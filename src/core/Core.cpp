/*
** EPITECH PROJECT, 2025
** video-code
** File description:
** Core
*/

#include "core/Core.hpp"

#include <pybind11/embed.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <argparse/argparse.hpp>
#include <chrono>
#include <cstddef>
#include <format>
#include <iostream>
#include <memory>
#include <nlohmann/json.hpp>
#include <string>

using json = nlohmann::json;

#include "core/Config.hpp"
#include "input/AInput.hpp"
#include "input/Camera.hpp"
#include "input/IInput.hpp"
#include "input/InputFactory.hpp"
#include "input/media/Image.hpp"
#include "input/media/Video.hpp"
// #include "input/media/Video.hpp"
#include "utils/Logger.hpp"
#include "vulkan/EffectResolver.hpp"
#include "window/VulkanWidget.hpp"

VC::Core::Core(const argparse::ArgumentParser& parser, const Config& config)
    : _showstack(parser.get<bool>("--showstack"))
    , _showtimeline(parser.get<bool>("--showtimeline"))
    , _config(config)
{
    reloadSourceFile();
}

VC::Core::Core(const Config& config)
    : _showstack(false)
    , _showtimeline(false)
    , _config(config)
{
}

// Recursively convert a Python object to nlohmann::json.
// Handles all types that can appear in StackAction args.
static json pyToJson(py::handle h)
{
    auto obj = py::reinterpret_borrow<py::object>(h);
    if (obj.is_none()) return nullptr;
    if (py::isinstance<py::bool_>(obj)) return obj.cast<bool>();
    if (py::isinstance<py::int_>(obj)) return obj.cast<int64_t>();
    if (py::isinstance<py::float_>(obj)) return obj.cast<double>();
    if (py::isinstance<py::str>(obj)) return obj.cast<std::string>();
    if (py::isinstance<py::dict>(obj)) {
        // `json::object()`, not a default-constructed json: that is NULL until
        // a key is written, so an input created with no arguments at all
        // reached AInput as a null and threw on the first `.at`. The list
        // branch below has always said `json::array()` for the same reason.
        json d = json::object();
        // Keys may be ints (Context.stack is keyed by inputIdx / frameIdx, with -1 the
        // Create sentinel) — stringify via py::str() rather than a direct cast.
        for (auto [k, v] : obj.cast<py::dict>())
            d[py::str(k).cast<std::string>()] = pyToJson(v);
        return d;
    }
    if (py::isinstance<py::list>(obj) || py::isinstance<py::tuple>(obj)) {
        json arr = json::array();
        for (auto item : obj)
            arr.push_back(pyToJson(item));
        return arr;
    }
    // Numeric types wrapping float (e.g. wufloat)
    if (py::hasattr(obj, "__float__")) {
        try {
            return obj.cast<double>();
        } catch (...) {
        }
    }
    // Custom types with explicit serialization (e.g. rgba → [r,g,b,a], v2 → {x,y}).
    // Must come before __dict__ so rgba doesn't become {"r":…} instead of [r,g,b,a].
    if (py::hasattr(obj, "jsonSerialization")) {
        return pyToJson(obj.attr("jsonSerialization")());
    }
    // Fallback: convert via __dict__ (StackAction subclasses)
    if (py::hasattr(obj, "__dict__")) {
        return pyToJson(obj.attr("__dict__"));
    }
    return obj.cast<std::string>();
}

void VC::Core::rebuildFromContext()
{
    const size_t savedIndex = _index;

    try {
        auto     ctx = py::module_::import("videocode.context").attr("Context");
        py::dict stack = ctx.attr("stack");
        py::list events = ctx.attr("events");

        executeStack(stack, events);

        // A Video may outlast the stack's own range.
        for (const auto& inputPtr : _inputs) {
            if (const Video* vid = dynamic_cast<const Video*>(inputPtr.get())) {
                if (vid->_origin + vid->_playbackLength > _nbFrame)
                    _nbFrame = vid->_origin + vid->_playbackLength;
            }
        }

        _lastRenderedIndex = SIZE_MAX;
        _cachedMeshes.clear();
        _anchorBoxes.clear();
    } catch (const py::error_already_set& e) {
        std::cerr << "\nError building the scene:\n"
                  << e.what() << "\n";
    }

    _index = (_nbFrame > 0) ? std::min(savedIndex, _nbFrame - 1) : 0;
}

void VC::Core::reloadSourceFile()
{
    size_t savedIndex = _index;

    // Startup timing — printed when compiled with -DVC_VERBOSE.
#ifdef VC_VERBOSE
    using Clock = std::chrono::high_resolution_clock;
    using Ms = std::chrono::duration<double, std::milli>;
    auto _t_reload = Clock::now();
    auto _t = Clock::now();
    auto _step = [&](const char* name) {
        double ms = std::chrono::duration_cast<Ms>(Clock::now() - _t).count();
        std::cout << std::format("[startup] {:35s} {:7.1f}ms\n", name, ms);
        _t = Clock::now();
    };
#else
    auto _step = [](const char*) {};
#endif

    _sceneFailed = false;
    try {
        auto serialize = py::module_::import("videocode.serialize");
        VC_TIME("execScene (in-process)", serialize.attr("execScene")(_config.sourceFile));
        _step("execScene (Python in-process)");

        auto     ctx = py::module_::import("videocode.context").attr("Context");
        py::dict stack = ctx.attr("stack");
        py::list events = ctx.attr("events");

        VC_TIME("executeStack", executeStack(stack, events));
        _step("executeStack (C++ reads py::dict)");

        // Extend _nbFrame to cover any Video inputs whose duration exceeds the stack's range.
        for (const auto& inputPtr : _inputs) {
            if (const Video* vid = dynamic_cast<const Video*>(inputPtr.get())) {
                if (vid->_origin + vid->_playbackLength > _nbFrame)
                    _nbFrame = vid->_origin + vid->_playbackLength;
            }
        }

        // Force a redraw with the (possibly partially-rebuilt) input set. Only invalidated
        // on success — a broken edit leaves the last-good render on screen instead of
        // blanking it.
        _lastRenderedIndex = SIZE_MAX;
        _cachedMeshes.clear();
        // The geometry a Space.ANCHOR box was derived from may have just been
        // edited — re-derive it against the new scene.
        _anchorBoxes.clear();

    } catch (const py::error_already_set& e) {
        std::cerr << "\nError in source file '" << _config.sourceFile << "':\n"
                  << e.what() << "\n";
        // Said, and remembered. Printing it was never the problem — nothing was
        // reading it, so `--generate` went on to encode nothing and call it a
        // success.
        _sceneFailed = true;
    }

    _index = (_nbFrame > 0) ? std::min(savedIndex, _nbFrame - 1) : 0;

#ifdef VC_VERBOSE
    double total_ms = std::chrono::duration_cast<Ms>(Clock::now() - _t_reload).count();
    std::cout << std::format("[startup] === reloadSourceFile() total: {:.1f}ms ===\n", total_ms);
#endif
}

void VC::Core::rebuildInput(size_t idx, const py::dict& inputData, bool reuseExisting)
{
    AInput*                 target = nullptr;
    std::unique_ptr<IInput> freshInput;

    if (reuseExisting && idx < _inputs.size())
        target = dynamic_cast<AInput*>(_inputs[idx].get());

    if (target) {
        // Create entry unchanged — keep the object alive (and its loaded media / GPU
        // descriptor / geometry caches) and just rewind its modification history.
        target->resetModifications();
    } else {
        py::dict create = inputData[py::int_(-1)].cast<py::dict>();
        auto     type = create["type"].cast<std::string>();
        json     args = pyToJson(create["args"]);

        if (_showstack)
            Debug.logStack({{"action", "Create"}, {"type", type}, {"args", args}});

        freshInput = Factory::inputs.at(type)(args);
        target = dynamic_cast<AInput*>(freshInput.get());
    }

    // Replay Apply entries by INCREASING FRAME, not in the dict's insertion order.
    //
    // AInput::add() carries a Metadata forward by copying the last one, so it is
    // only correct if the frames arrive in order — and the dict's order is the
    // order the statements were written, which is not the same thing. A frame
    // added after a later one loses the frames in between.
    //
    // It already happens: `scene.py` inserts frame 57 after frame 92 on both of
    // its members, because `autodestroy` drops a no-op frame on the first pass and
    // the chained pass re-emits it once the cursor has moved. It is harmless there
    // only because the late frame carries exactly what the carry would have given
    // — a coincidence of values, not a protection.
    //
    // Sorting costs one pass and closes the whole class. Note the asymmetry it
    // repairs: the incremental-reload check below compares dicts WITHOUT regard to
    // insertion order, while this replay depended on it.
    std::vector<std::pair<ssize_t, py::handle>> byFrame;
    byFrame.reserve(inputData.size());
    for (auto [rawFrame, rawShaders] : inputData) {
        ssize_t frameIdx = rawFrame.cast<ssize_t>();
        if (frameIdx < 0) continue; // skip Create sentinel at -1
        byFrame.emplace_back(frameIdx, rawShaders);
    }
    std::sort(byFrame.begin(), byFrame.end(), [](const auto& a, const auto& b) { return a.first < b.first; });

    for (auto& [frameIdx, rawShaders] : byFrame) {
        for (auto [rawKey, rawEntry] : rawShaders.cast<py::dict>()) {
            std::string dictKey = rawKey.cast<std::string>();
            // "Args:argName" → shaderName = "Args"; everything else is verbatim.
            std::string shaderName = dictKey.substr(0, dictKey.find(':'));

            json        entry = pyToJson(py::reinterpret_borrow<py::object>(rawEntry));
            std::string shaderType = entry["type"].get<std::string>();

            if (_showstack)
                Debug.logStack({{"action", "Apply"}, {"input", (ssize_t)idx}, {"name", shaderName}, {"type", shaderType}, {"args", entry["args"]}});

            target->add(shaderName, shaderType, std::move(entry["args"].get_ref<json::object_t&>()));
        }
    }

    // Only freshly-constructed Image/Video need a texture (re)upload — a reused input's
    // descriptor still points at the same (unchanged) media and remains valid.
    if (freshInput) {
        if (idx >= _inputs.size())
            _inputs.resize(idx + 1);

        if (dynamic_cast<Image*>(freshInput.get()) || dynamic_cast<Video*>(freshInput.get()))
            _pendingTextureUpload.push_back(idx);

        _inputs[idx] = std::move(freshInput);
    }
}

void VC::Core::executeStack(const py::dict& stack, const py::list& events)
{
    // Read total frame count from Python — avoids iterating all 17k+ stack entries as JSON.
    _nbFrame = py::module_::import("videocode.context")
                   .attr("Context")
                   .attr("lastEverAffectedFrame")
                   .cast<size_t>();

    // A scene that animates nothing still has a frame to show: everything lands
    // on frame 0 with no duration, so the cursor never leaves 0 and this wrote a
    // video with no frames in it at all.
    _nbFrame = std::max<size_t>(_nbFrame, 1);

    // Clear color from the script's `BG` global (Context.backgroundColor,
    // resolved by serialize.py after the scene ran). Reset to the default
    // unconditionally: a hot-reload that removed BG must restore the gray.
    py::object bg = py::module_::import("videocode.context").attr("Context").attr("backgroundColor");
    if (bg.is_none()) {
        _bgColor = {0.2f, 0.2f, 0.2f};
    } else {
        py::tuple t = bg.cast<py::tuple>();
        _bgColor = {t[0].cast<float>(), t[1].cast<float>(), t[2].cast<float>()};
    }

    // Only diff input-by-input when the set of input indices is unchanged — adding/
    // removing an input reshuffles Python's sequential index counter, so positional
    // diffing would silently compare unrelated inputs. Fall back to a full rebuild then.
    bool sameIndexSet = (_pySnapshot.size() == stack.size());
    if (sameIndexSet) {
        for (auto [rawIdx, _] : stack) {
            if (!_pySnapshot.contains(rawIdx)) {
                sameIndexSet = false;
                break;
            }
        }
    }

    _pendingTextureUpload.clear();
    if (!sameIndexSet) {
        _inputs.clear();
        _inputs.resize(stack.size());
        _pySnapshot = py::dict();
    }

    py::dict newPySnapshot;

    for (auto [rawIdx, rawInputData] : stack) {
        int        idx = py::reinterpret_borrow<py::object>(rawIdx).cast<int>();
        py::object inputObj = py::reinterpret_borrow<py::object>(rawInputData);
        py::dict   inputData = inputObj.cast<py::dict>();

        bool known = sameIndexSet && _pySnapshot.contains(rawIdx);

        if (known) {
            // Python dict equality — far cheaper than pyToJson()+nlohmann::json::operator==
            // for inputs with many per-frame shaders (e.g. animated Plane elements).
            py::object prevData = _pySnapshot[rawIdx];
            if (PyObject_RichCompareBool(prevData.ptr(), inputObj.ptr(), Py_EQ) == 1) {
                newPySnapshot[rawIdx] = inputObj;
                continue; // nothing changed — keep existing AInput and its caches
            }
        }

        // Reuse the existing object (skip its constructor — e.g. Image/Video file I/O)
        // when only its modifications changed, i.e. its Create entry ("-1") is identical.
        bool reuseExisting = false;
        if (known) {
            py::object prevData = _pySnapshot[rawIdx];
            py::int_   createKey(-1);
            auto       prevDict = prevData.cast<py::dict>();
            if (prevDict.contains(createKey) && inputData.contains(createKey)) {
                py::object prevCreate = prevDict[createKey];
                py::object newCreate = inputData[createKey];
                reuseExisting = PyObject_RichCompareBool(prevCreate.ptr(), newCreate.ptr(), Py_EQ) == 1;
            }
        }

        rebuildInput((size_t)idx, inputData, reuseExisting);
        newPySnapshot[rawIdx] = inputObj;
    }

    _pySnapshot = std::move(newPySnapshot);

    // Pass 3: Wait and Timestamp events (absolute positions stored by Python).
    _clockStops = {};
    _timestamps.clear();
    for (const auto& item : events) {
        auto obj = py::reinterpret_borrow<py::object>(item);
        auto action = obj.attr("action").cast<std::string>();

        if (action == "Wait") {
            // A wait is a SCHEDULING GAP: scheduled state holds by itself
            // (the metas/args step-function keeps its last value) and the
            // timeline extends. Its `stop` list names the ambient clocks
            // paused for the span (empty = everything keeps living;
            // freeze() = all of them). Paused clocks resume where they
            // stopped — pause, not skip.
            size_t start = obj.attr("start").cast<size_t>();
            size_t n = obj.attr("n").cast<size_t>();
            for (auto rawStop : obj.attr("stop")) {
                std::string clock = py::str(rawStop).cast<std::string>();
                if (clock == "videos")
                    _clockStops.videos.push_back({start, n});
                else if (clock == "paints")
                    _clockStops.paints.push_back({start, n});
                else if (clock == "effects")
                    _clockStops.effects.push_back({start, n});
            }
            size_t waitEnd = start + n;
            if (waitEnd > _nbFrame)
                _nbFrame = waitEnd;

        } else if (action == "Timestamp") {
            auto   name = obj.attr("name").cast<std::string>();
            size_t time = obj.attr("time").cast<size_t>();
            _timestamps[time] = name;
        }
    }
}

Camera2D VC::Core::cameraAt(size_t frame) const
{
    for (const auto& i : _inputs)
        if (auto* cam = dynamic_cast<::Camera*>(i.get()))
            return cameraFromMetadata(cam->getMetadata(frame));
    return {};
}

const ShaderBox& VC::Core::anchorBoxFor(size_t inputIndex, size_t since)
{
    auto key = std::make_pair(inputIndex, since);
    auto it = _anchorBoxes.find(key);
    if (it != _anchorBoxes.end())
        return it->second;

    // Re-derive rather than remember: run the SAME metadata → mesh path the
    // renderer runs, at the declared frame. Deterministic, so scrubbing back
    // and forth or hot-reloading can never shift a pinned pattern; the map is
    // only there to keep an anchored paint from re-tessellating its host on
    // every frame.
    auto&    input = _inputs[inputIndex];
    Metadata meta = input->getMetadata(since);
    meta.frameIndex = since - ClockStops::pausedBefore(_clockStops.videos, since);

    Mesh mesh = input->getMesh(meta, _config);
    // The box is where the host WAS on screen at `since` — so it is measured
    // through the camera of that frame, not this one. Same rule as the box
    // itself: a pure function of a declared frame.
    mesh.camera = meta.pinnedToFrame ? Camera2D{} : cameraAt(since);

    return _anchorBoxes.emplace(key, meshBoxUV(mesh)).first->second;
}

const std::vector<Mesh>& VC::Core::generateMeshes()
{
    size_t renderIndex = _index;

    if (renderIndex != _lastRenderedIndex) {
        _cachedMeshes.clear();
        // Resolved before the loop, not inside it: the camera input sits
        // wherever the scene first moved it, which may be after the meshes it
        // has to be applied to.
        const Camera2D sceneCamera = cameraAt(renderIndex);
        VC_TIME("generateMeshes", {
            for (auto& i : _inputs) {
#ifdef VC_DEBUG_ON
                auto _tInput0 = std::chrono::high_resolution_clock::now();
#endif
                // Never drawn: it is the frame everything else is drawn in.
                if (dynamic_cast<::Camera*>(i.get()))
                    continue;

                auto meta = i->getMetadata(renderIndex);
                // Video playback runs on the VIDEOS ambient clock — pause
                // spans (wait(stop=Clock.VIDEOS)/freeze) subtract out here;
                // frameIndex's only consumer is Video::getMesh.
                meta.frameIndex = renderIndex - ClockStops::pausedBefore(_clockStops.videos, renderIndex);
                // A composition layer is emitted even hidden or at opacity 0: its
                // members are drawn ONLY through it, so dropping the layer
                // would orphan them and they would reappear at full strength.
                // Both states ride on compOpacity below instead.
                if (meta.isComposition || (!meta.hidden && meta.opacity != 0)) {
                    auto mesh = i->getMesh(meta, _config);
                    if (auto* a = dynamic_cast<AInput*>(i.get())) {
                        mesh.effects = a->getActiveEffectsAtFrame(renderIndex, _clockStops);
                        // A paint pinned with Space.ANCHOR needs the box of a
                        // frame that is not this one. Only Core can produce it
                        // (it owns the inputs), so it travels on the effect —
                        // the resolver never sees an input.
                        for (auto& eff : mesh.effects)
                            if (eff.space == ShaderSpace::Anchor)
                                eff.anchorBox = anchorBoxFor(
                                    static_cast<size_t>(&i - &_inputs[0]),
                                    std::min(meta.fillShaderSince, renderIndex)
                                );
                    }
                    // Default zIndex = creation order, matching the
                    // Python-side default (Metadata.zIndex = self.index).
                    mesh.zIndex = meta.zIndexExplicit ? meta.zIndex : static_cast<int>(&i - &_inputs[0]);
                    mesh.zOrderSeq = meta.zOrderSeq;
                    mesh.blendMode = meta.blendMode;
                    // Carry input identity + matte reference (same _inputs[]
                    // index expression as the default zIndex above) so the
                    // renderer can resolve a matte consumer's source mesh.
                    mesh.inputIndex = static_cast<int>(&i - &_inputs[0]);
                    mesh.matteSourceInputIndex = meta.matteSource;
                    mesh.isAdjustmentLayer = meta.isAdjustmentLayer;
                    mesh.isComposition = meta.isComposition;
                    mesh.compositionIndex = meta.compositionIndex;
                    mesh.compOpacity = meta.hidden ? 0.f : meta.opacity / 255.f;
                    // pinToFrame() is spent here: the mesh keeps the identity
                    // and the vertex stage never learns the scene moved.
                    mesh.camera = meta.pinnedToFrame ? Camera2D{} : sceneCamera;
                    _cachedMeshes.push_back(std::move(mesh));
                }
#ifdef VC_DEBUG_ON
                auto _tInputMs = std::chrono::duration_cast<std::chrono::microseconds>(
                                     std::chrono::high_resolution_clock::now() - _tInput0
                )
                                     .count();
                if (_tInputMs > 500)
                    VC_LOG(std::format("[timer] getMesh input#{}: {}µs\n", &i - &_inputs[0], _tInputMs));
#endif
            }
        });
        // Sort by zIndex ascending (lower = further behind). Ties broken by
        // zOrderSeq: the zIndex changed most recently wins (renders on top).
        std::stable_sort(_cachedMeshes.begin(), _cachedMeshes.end(), [](const Mesh& a, const Mesh& b) {
            if (a.zIndex != b.zIndex)
                return a.zIndex < b.zIndex;
            return a.zOrderSeq < b.zOrderSeq;
        });
        _lastRenderedIndex = renderIndex;
        _meshesRebuilt = true;
    } else {
        _meshesRebuilt = false;
    }

    // load next frame if not in pause and not at the end
    if (_paused == false && _nbFrame && _index < _nbFrame - 1) {
        _index += 1;
        _indexChanged = true;
    } else {
        _indexChanged = false;
    }

    return _cachedMeshes;
}

#define currIndex(i, s) (s == 0 ? 0 : (i + 1))

void VC::Core::pause()
{
    _paused = !_paused;
    _indexChanged = true;
    std::cout << std::format("Timeline {} at frame {}/{}.", _paused ? "paused" : "unpaused", currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::goToFirstFrame()
{
    if (_index != 0) {
        _index = 0;
        _indexChanged = true;
    }
    std::cout << std::format("Jumped backward to the first frame {}/{}.", currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::goToLastFrame()
{
    if (_nbFrame != 0) {
        _index = _nbFrame - 1;
        _indexChanged = true;
    }
    std::cout << std::format("Jumped forward to the last frame {}/{}.", currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::goToPrevTimestamp()
{
    auto it = _timestamps.lower_bound(_index);

    if (it == _timestamps.begin()) {
        return;
    }

    --it;

    // Skip the frame we just jumped to only on a quick double-press (< 2s).
    // After 2s the user has settled on that timestamp, so treat it as the new base.
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - _lastJumpTime).count();
    if (it->first == _lastJumpedFrame && it != _timestamps.begin() && elapsed < 2000) {
        --it;
    }

    auto index = it->first;
    auto name = it->second;

    if (_index < _nbFrame && _index >= 0) {
        _lastJumpedFrame = index;
        _lastJumpTime = now;
        _index = index;
        _indexChanged = true;
    }

    std::cout << std::format("Jumped backward to the timestamp {} at frame {}/{}.", name, currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::goToNextTimestamp()
{
    auto it = _timestamps.lower_bound(_index);

    if (it == _timestamps.end()) {
        return;
    }

    auto index = it->first;
    auto name = it->second;

    if (_index < _nbFrame && _index >= 0) {
        _lastJumpedFrame = index;
        _index = index;
        _indexChanged = true;
    }

    std::cout << std::format("Jumped forward to the timestamp {} at frame {}/{}.", name, currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::backwardFrame(size_t n)
{
    if (_index >= n) {
        _index -= n;
        _indexChanged = true;
    } else {
        goToFirstFrame();
        return;
    }
    std::cout << std::format("Jumped backward to the frame {}/{}.", currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::forwardFrame(size_t n)
{
    if (n < _nbFrame - _index) {
        _index += n;
        _indexChanged = true;
    } else {
        goToLastFrame();
        return;
    }
    std::cout << std::format("Jumped forward to the frame {}/{}.", currIndex(_index, _nbFrame), _nbFrame) << std::endl;
}

void VC::Core::uploadTextures(VC::VulkanWidget* widget)
{
    // Only (re)upload textures for inputs rebuilt by the last executeStack() — reusing
    // an unchanged Image/Video's existing descriptor set avoids leaking GPU textures.
    for (size_t idx : _pendingTextureUpload) {
        IInput* inputPtr = _inputs[idx].get();
        if (Image* img = dynamic_cast<Image*>(inputPtr)) {
            VkDescriptorSet desc = widget->uploadTexture(img->getBase());
            img->setTextureDescriptor(desc);
        } else if (Video* vid = dynamic_cast<Video*>(inputPtr)) {
            VkDescriptorSet desc = widget->uploadTexture(vid->currentFrame());
            vid->setDescriptor(desc);
            vid->setReuploadFn([widget, desc](const cv::Mat& mat) {
                widget->updateTexturePixels(desc, mat);
            });
        }
    }
    _pendingTextureUpload.clear();
}

void VC::Core::requeueTextures()
{
    // The cached meshes carry the descriptors of the renderer that was just
    // destroyed: drawn again at the same frame, they bound freed sets.
    _lastRenderedIndex = SIZE_MAX;
    _cachedMeshes.clear();
    _pendingTextureUpload.clear();
    for (size_t idx = 0; idx < _inputs.size(); ++idx)
        if (dynamic_cast<Image*>(_inputs[idx].get()) || dynamic_cast<Video*>(_inputs[idx].get()))
            _pendingTextureUpload.push_back(idx);
}

void VC::Core::uploadTextures(
    std::function<VkDescriptorSet(const cv::Mat&)>       uploadFn,
    std::function<void(VkDescriptorSet, const cv::Mat&)> reuploadFn
)
{
    for (size_t idx : _pendingTextureUpload) {
        IInput* inputPtr = _inputs[idx].get();
        if (Image* img = dynamic_cast<Image*>(inputPtr)) {
            img->setTextureDescriptor(uploadFn(img->getBase()));
        } else if (Video* vid = dynamic_cast<Video*>(inputPtr)) {
            VkDescriptorSet desc = uploadFn(vid->currentFrame());
            vid->setDescriptor(desc);
            if (reuploadFn) {
                vid->setReuploadFn([desc, reuploadFn](const cv::Mat& mat) {
                    reuploadFn(desc, mat);
                });
            }
        }
    }
    _pendingTextureUpload.clear();
}
