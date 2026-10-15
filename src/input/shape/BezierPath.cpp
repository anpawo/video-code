/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** BezierPath
*/

#include "input/shape/BezierPath.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <functional>
#include <mapbox/earcut.hpp>

#include "utils/Color.hpp"
#include "utils/Logger.hpp"
#include "vulkan/MeshFactory.hpp"

#ifdef VC_DEBUG_ON
    #include <chrono>
    #define BP_T(name) auto name = std::chrono::high_resolution_clock::now()
    #define BP_US(a, b) std::chrono::duration_cast<std::chrono::microseconds>((b) - (a)).count()
#else
    #define BP_T(name) [[maybe_unused]] int name = 0
    #define BP_US(a, b) 0L
#endif

BezierPath::BezierPath(json::object_t&& args)
    : AInput(std::move(args))
{
}

// FNV-1a 64-bit hash over raw bytes, chainable (pass previous hash as seed).
static size_t fnvHash(const void* data, size_t bytes, size_t h = 0xcbf29ce484222325ULL)
{
    constexpr size_t PRIME = 0x00000100000001B3ULL;
    const auto*      p = static_cast<const uint8_t*>(data);
    for (size_t i = 0; i < bytes; ++i)
        h = (h ^ p[i]) * PRIME;
    return h;
}

// Sutherland-Hodgman polygon clip against a single half-plane.
// insideIsAbove=true keeps vertices where (p · dir) >= threshold.
// insideIsAbove=false keeps vertices where (p · dir) <= threshold.
// Works correctly for convex inputs; simple (non-self-intersecting) for typical
// non-convex inputs encountered in practice (rectangles, circles, arrows).
static std::vector<cv::Vec2f> clipPolyHalfPlane(
    const std::vector<cv::Vec2f>& poly,
    const cv::Vec2f&              dir,
    float                         threshold,
    bool                          insideIsAbove
)
{
    if (poly.empty()) return {};
    std::vector<cv::Vec2f> out;
    out.reserve(poly.size() + 1);
    size_t n = poly.size();
    for (size_t i = 0; i < n; ++i) {
        const cv::Vec2f& a = poly[i];
        const cv::Vec2f& b = poly[(i + 1) % n];
        float            pa = a[0] * dir[0] + a[1] * dir[1];
        float            pb = b[0] * dir[0] + b[1] * dir[1];
        bool             ia = insideIsAbove ? (pa >= threshold) : (pa <= threshold);
        bool             ib = insideIsAbove ? (pb >= threshold) : (pb <= threshold);
        if (ia)
            out.push_back(a);
        if (ia != ib) {
            float alpha = (threshold - pa) / (pb - pa);
            out.push_back(a + alpha * (b - a));
        }
    }
    return out;
}

// Earcuts a FillGroup (outer ring + holes) and returns the resulting triangles
// as raw point triples, in local space. Used by radial/conic fills to build
// hole-respecting geometry — earcut-with-holes naturally excludes the hole
// interiors from the triangulation.
static std::vector<std::array<cv::Vec2f, 3>> triangulateGroup(const BezierPath::FillGroup& group)
{
    std::vector<std::vector<std::array<float, 2>>> polygon;
    polygon.reserve(1 + group.holes.size());

    auto addRing = [&](const std::vector<cv::Vec2f>& r) {
        std::vector<std::array<float, 2>> ring;
        ring.reserve(r.size());
        for (const auto& p : r)
            ring.push_back({p[0], p[1]});
        polygon.push_back(std::move(ring));
    };
    addRing(group.outer);
    for (const auto& hole : group.holes)
        addRing(hole);

    auto indices = mapbox::earcut<uint32_t>(polygon);

    auto pointAt = [&](uint32_t idx) -> cv::Vec2f {
        for (const auto& ring : polygon) {
            if (idx < ring.size())
                return {ring[idx][0], ring[idx][1]};
            idx -= static_cast<uint32_t>(ring.size());
        }
        return {0.f, 0.f};
    };

    std::vector<std::array<cv::Vec2f, 3>> triangles;
    triangles.reserve(indices.size() / 3);
    for (size_t i = 0; i + 2 < indices.size(); i += 3)
        triangles.push_back({pointAt(indices[i]), pointAt(indices[i + 1]), pointAt(indices[i + 2])});
    return triangles;
}

// Recursively splits triangle (v0,v1,v2) via midpoint subdivision until the
// gradient value tFn() varies by less than `epsilon` across its vertices (or
// `maxDepth` is reached), then emits the (possibly subdivided) leaf triangles
// via `emit(p, color)` — called 3 times per leaf, in winding order.
//
// `wrapT` selects wrap-aware delta (conic: t wraps at 1→0, so a triangle
// straddling the seam has vertices near both 0 and 1 — treated as close).
// Radial `t` never wraps, so plain |a-b| is used.
static void subdivideGradientTriangle(
    cv::Vec2f v0, cv::Vec2f v1, cv::Vec2f v2,
    const std::function<float(cv::Vec2f)>& tFn,
    const std::vector<GradientStop>&       stops,
    int depth, int maxDepth, float epsilon, bool wrapT,
    const std::function<void(cv::Vec2f, cv::Vec4b)>& emit
)
{
    float t0 = tFn(v0), t1 = tFn(v1), t2 = tFn(v2);

    auto delta = [wrapT](float a, float b) {
        float d = std::abs(a - b);
        return wrapT ? std::min(d, 1.f - d) : d;
    };

    cv::Vec2f m01 = 0.5f * (v0 + v1);
    cv::Vec2f m12 = 0.5f * (v1 + v2);
    cv::Vec2f m20 = 0.5f * (v2 + v0);

    // Vertex-pairwise deltas alone miss "fan" triangles whose 3 vertices sit on
    // (or near) the same isoline but whose interior bulges toward/away from
    // center (e.g. an earcut ear spanning a wide arc of the outer ring) — such
    // a triangle would pass a vertex-only flat check and get painted a single
    // solid color despite its interior covering a wide range of t. Catch this
    // by also comparing each edge midpoint's *actual* t against the linear
    // (vertex-average) estimate: a large mismatch means tFn is curved across
    // this triangle, so it still needs subdividing.
    bool flat = std::max({delta(t0, t1), delta(t1, t2), delta(t0, t2)}) < epsilon;
    if (flat) {
        float tm01 = tFn(m01), tm12 = tFn(m12), tm20 = tFn(m20);
        flat = delta(tm01, 0.5f * (t0 + t1)) < epsilon && delta(tm12, 0.5f * (t1 + t2)) < epsilon && delta(tm20, 0.5f * (t2 + t0)) < epsilon;
    }

    if (depth >= maxDepth || flat) {
        emit(v0, lerpGradient(stops, t0));
        emit(v1, lerpGradient(stops, t1));
        emit(v2, lerpGradient(stops, t2));
        return;
    }

    subdivideGradientTriangle(v0, m01, m20, tFn, stops, depth + 1, maxDepth, epsilon, wrapT, emit);
    subdivideGradientTriangle(m01, v1, m12, tFn, stops, depth + 1, maxDepth, epsilon, wrapT, emit);
    subdivideGradientTriangle(m20, m12, v2, tFn, stops, depth + 1, maxDepth, epsilon, wrapT, emit);
    subdivideGradientTriangle(m01, m12, m20, tFn, stops, depth + 1, maxDepth, epsilon, wrapT, emit);
}

void BezierPath::parseColorOrGradient(
    const json::object_t& args, const std::string& key,
    cv::Vec4b& color, std::vector<GradientStop>& stops, GradType& gradType, float& angle
)
{
    const auto& colorJson = args.at(key);

    // A PaintShader fill (fillColor = silk()/fire()/... on the Python side)
    // serializes as an object with a "shader" key: the geometry renders as
    // opaque white — full coverage for the shader (injected per-frame by
    // AInput::getActiveEffectsAtFrame) to replace, keeping only the alpha.
    if (colorJson.is_object()) {
        color = {255, 255, 255, 255};
        stops.clear();
        gradType = GradType::None;
        return;
    }

    // LinearGradient / RadialGradient / ConicGradient emit [stops_array, discriminator].
    // Linear:  discriminator is a number (the angle in degrees).
    // Radial:  discriminator is the string "radial".
    // Conic:   discriminator is ["conic", angle_in_degrees].
    // Solid rgba is a flat 4-element number array.
    if (colorJson.is_array() && colorJson.size() == 2 && colorJson[0].is_array()) {
        const auto& stopsJson = colorJson[0];
        stops.clear();
        stops.reserve(stopsJson.size());
        for (const auto& stopJson : stopsJson) {
            stops.push_back(GradientStop{
                colorFromJson(stopJson[0], 255),
                stopJson[1].get<float>() / 100.f,
            });
        }
        if (colorJson[1].is_string()) {
            gradType = GradType::Radial;
        } else if (colorJson[1].is_array()) {
            angle = colorJson[1][1].get<float>();
            gradType = GradType::Conic;
        } else {
            angle = colorJson[1].get<float>();
            gradType = GradType::Linear;
        }
    } else {
        color = colorFromJson(colorJson, 255);
        stops.clear();
        gradType = GradType::None;
    }
}

void BezierPath::buildPath(const Metadata& meta)
{
    const auto& args = meta.args();

    _strokeWidth = args.at("strokeWidth").get<float>() * config::worldToPixelRatio;
    parseColorOrGradient(args, "fillColor", _fillColor, _fillStops, _fillGradType, _fillGradientAngle);
    parseColorOrGradient(args, "strokeColor", _strokeColor, _strokeStops, _strokeGradType, _strokeGradientAngle);
    // Open paths (Curve, …): stroke only, no closing segment, and the points
    // keep their absolute coordinates (no bbox normalization in getMesh).
    _closed = !(args.contains("open") && args.at("open").get<bool>());

    // Multi-contour shapes (letter glyphs): point count per contour.
    _contourSizes = meta.contourSizesPtr ? *meta.contourSizesPtr : std::vector<size_t>{};

    const auto& points = meta.pointsPtr ? *meta.pointsPtr : std::vector<cv::Vec2f>{};
    if (points.size() >= 4 && points.size() % 2 == 0)
        _points = points;
    // else: leave _points unchanged — Image/Video's getMesh() falls back to
    // their legacy quad when no usable points are supplied.

    // Textured fills (Image/Video) — UV mapping mode. Polygon doesn't push
    // these args, so default to Stretch when absent.
    if (args.contains("uvMapping")) {
        const std::string& mode = args.at("uvMapping").get_ref<const std::string&>();
        _uvMapping = (mode == "radial") ? UVMapping::Radial : (mode == "conic") ? UVMapping::Conic
                                                                                : UVMapping::Stretch;
    }
    if (args.contains("uvAngle"))
        _uvAngle = args.at("uvAngle").get<float>();
}

Mesh BezierPath::getMesh(const Metadata& meta, const Config& config)
{
    BP_T(t0);

    // --- Fast path: skip buildPath entirely when args are known static ----------
    // meta.argsStatic is true when no "Args" VertexShader has ever fired for this
    // input, so _baseArgs (and therefore _points) can never have changed.
    if (!meta.argsStatic || !_geomValid) {
        _points.clear();
        buildPath(meta);
    }

    BP_T(t1);

    size_t n = _points.size();
    if (n < 4 || n % 2 != 0) {
        _meshCacheValid = false;
        return {};
    }

    // --- Geometry cache --------------------------------------------------------
    // Key: _points bytes + scale.x/y + rotation + fill/stroke visibility.
    // Fill sampling (localPoly/earIndices) only runs when fill is non-transparent,
    // so a transparency change must bust the cache.
    size_t geomHash = fnvHash(_points.data(), n * sizeof(cv::Vec2f));
    geomHash = fnvHash(&meta.scale.x, sizeof(float), geomHash);
    geomHash = fnvHash(&meta.scale.y, sizeof(float), geomHash);
    geomHash = fnvHash(&meta.rotation, sizeof(float), geomHash);
    auto anyStopVisible = [](const std::vector<GradientStop>& stops) {
        return std::any_of(stops.begin(), stops.end(), [](const GradientStop& s) { return s.color[3] > 0; });
    };
    // Open paths never fill — there is no interior to triangulate. Textured
    // shapes (Image/Video) always have fill geometry to sample into, regardless
    // of _fillColor's alpha.
    bool hasFillNow = _closed && (isTextured() || ((_fillGradType != GradType::None) ? anyStopVisible(_fillStops) : _fillColor[3] > 0));
    geomHash = fnvHash(&hasFillNow, sizeof(bool), geomHash);
    if (!_contourSizes.empty())
        geomHash = fnvHash(_contourSizes.data(), _contourSizes.size() * sizeof(size_t), geomHash);

    // --- Mesh-level cache check --------------------------------------------
    // Extends geomHash with the remaining fields MeshFactory's output depends
    // on, besides meta.position/meta.opacity (handled below via a cheap delta).
    size_t meshHash = geomHash;
    meshHash = fnvHash(&_fillColor, sizeof(_fillColor), meshHash);
    meshHash = fnvHash(&_strokeColor, sizeof(_strokeColor), meshHash);
    meshHash = fnvHash(&_strokeWidth, sizeof(_strokeWidth), meshHash);
    meshHash = fnvHash(&meta.align.x, sizeof(float), meshHash);
    meshHash = fnvHash(&meta.align.y, sizeof(float), meshHash);
    if (!_fillStops.empty())
        meshHash = fnvHash(_fillStops.data(), _fillStops.size() * sizeof(GradientStop), meshHash);
    if (!_strokeStops.empty())
        meshHash = fnvHash(_strokeStops.data(), _strokeStops.size() * sizeof(GradientStop), meshHash);
    if (isTextured()) {
        meshHash = fnvHash(&_uvMapping, sizeof(_uvMapping), meshHash);
        meshHash = fnvHash(&_uvAngle, sizeof(_uvAngle), meshHash);
    }

    // --- Shape-only hash (everything MeshFactory's output depends on *except*
    // the M-dependent transform fields: scale, rotation, align, position,
    // opacity). A match means the cached mesh's geometry/colors are still
    // correct and only need re-placing via the affine delta below.
    size_t shapeHash = fnvHash(_points.data(), n * sizeof(cv::Vec2f));
    shapeHash = fnvHash(&hasFillNow, sizeof(bool), shapeHash);
    if (!_contourSizes.empty())
        shapeHash = fnvHash(_contourSizes.data(), _contourSizes.size() * sizeof(size_t), shapeHash);
    shapeHash = fnvHash(&_fillColor, sizeof(_fillColor), shapeHash);
    shapeHash = fnvHash(&_strokeColor, sizeof(_strokeColor), shapeHash);
    shapeHash = fnvHash(&_strokeWidth, sizeof(_strokeWidth), shapeHash);
    if (!_fillStops.empty())
        shapeHash = fnvHash(_fillStops.data(), _fillStops.size() * sizeof(GradientStop), shapeHash);
    if (!_strokeStops.empty())
        shapeHash = fnvHash(_strokeStops.data(), _strokeStops.size() * sizeof(GradientStop), shapeHash);
    if (isTextured()) {
        shapeHash = fnvHash(&_uvMapping, sizeof(_uvMapping), shapeHash);
        shapeHash = fnvHash(&_uvAngle, sizeof(_uvAngle), shapeHash);
    }

    if (_meshCacheValid && shapeHash == _lastShapeHash && _meshCacheOpacity > 0 && _meshCacheScreen.width == config.screenWidth && _meshCacheScreen.height == config.screenHeight) {
        bool sameTransform = meta.position.x == _meshCachePosition[0] && meta.position.y == _meshCachePosition[1] && meta.scale.x == _meshCacheScale[0] && meta.scale.y == _meshCacheScale[1] && meta.rotation == _meshCacheRotation && meta.align.x == _meshCacheAlign[0] && meta.align.y == _meshCacheAlign[1];
        bool uniformOld = _meshCacheScale[0] == _meshCacheScale[1] && _meshCacheScale[0] != 0.f;
        bool uniformNew = meta.scale.x == meta.scale.y && meta.scale.x != 0.f;

        if (sameTransform || (uniformOld && uniformNew)) {
            Mesh  mesh = _meshCache;
            float opacityRatio = meta.opacity / static_cast<float>(_meshCacheOpacity);
            // Not part of the hash: the preview's renderer is rebuilt at each
            // new pane size and uploads the texture again, under a new set.
            if (isTextured())
                mesh.textureDescriptor = textureDescriptor();

            if (!sameTransform) {
                // D = T_ndc * M_new * M_old^-1 * T_ndc^-1. For uniform-scale
                // M_old/M_new, M_new*M_old^-1 is a similarity transform (rotation
                // + uniform scale) in pixel space, which commutes with stroke
                // extrusion (halfW and join geometry scale by the same factor as
                // the centerline). Conjugating into NDC space by the fixed
                // per-axis NDC scale preserves that, so applying D to the cached
                // NDC vertices reproduces a full rebuild at meta's transform.
                Metadata oldMeta = meta;
                oldMeta.position = {_meshCachePosition[0], _meshCachePosition[1]};
                oldMeta.scale = {_meshCacheScale[0], _meshCacheScale[1]};
                oldMeta.rotation = _meshCacheRotation;
                oldMeta.align = {_meshCacheAlign[0], _meshCacheAlign[1]};

                cv::Matx33f Mold = getTransformationMatrixFromMetadata(_geomCache.localSize, oldMeta);
                cv::Matx33f Mnew = getTransformationMatrixFromMetadata(_geomCache.localSize, meta);
                float       hw = config.screenWidth / 2.f;
                float       hh = config.screenHeight / 2.f;
                cv::Matx33f Tndc{
                    1.f / hw,
                    0.f,
                    -1.f,
                    0.f,
                    1.f / hh,
                    -1.f,
                    0.f,
                    0.f,
                    1.f,
                };
                cv::Matx33f D = Tndc * Mnew * Mold.inv() * Tndc.inv();

                for (auto& v : mesh.vertices) {
                    cv::Matx31f p = D * cv::Matx31f{v.pos[0], v.pos[1], 1.f};
                    v.pos[0] = p(0);
                    v.pos[1] = p(1);
                }
            }
            if (opacityRatio != 1.f) {
                for (auto& v : mesh.vertices)
                    v.color[3] *= opacityRatio;
            }
            return mesh;
        }
        // else: non-uniform scale change on either side — fall through to a
        // full rebuild (stroke extrusion doesn't commute with D in that case).
    }

    if (!_geomValid || geomHash != _lastGeomHash) {
        // Partition _points into contours (default: a single one). Invalid
        // partitions (bad sum / odd or tiny chunks) fall back to one contour.
        std::vector<size_t> sizes = _contourSizes;
        {
            size_t sum = 0;
            bool   valid = !sizes.empty();
            for (size_t s : sizes) {
                sum += s;
                if (s < 4 || s % 2 != 0)
                    valid = false;
            }
            if (!valid || sum != n)
                sizes = {n};
        }

        // Build quadratic bezier segments per contour from the anchor-handle
        // pairs. Open paths drop the wrap-around segment (their final handle
        // is a dummy that only terminates the pair format).
        std::vector<QuadraticBezier2D>         curves;
        std::vector<std::pair<size_t, size_t>> contourCurves;
        curves.reserve(n / 2);
        size_t base = 0;
        for (size_t s : sizes) {
            size_t segs = _closed ? s / 2 : s / 2 - 1;
            size_t first = curves.size();
            for (size_t i = 0; i < segs; ++i) {
                curves.push_back({
                    _points[base + 2 * i],
                    _points[base + 2 * i + 1],
                    _points[base + (2 * i + 2) % s],
                });
            }
            contourCurves.push_back({first, segs});
            base += s;
        }

        // Bounding box of control points.
        float minX = _points[0][0], maxX = _points[0][0];
        float minY = _points[0][1], maxY = _points[0][1];
        for (const auto& p : _points) {
            minX = std::min(minX, p[0]);
            maxX = std::max(maxX, p[0]);
            minY = std::min(minY, p[1]);
            maxY = std::max(maxY, p[1]);
        }

        // Shift all control points so the bounding box starts at (0,0).
        // Open paths skip the shift: their points keep absolute coordinates
        // so position() acts as a pure translation (Graph curves rely on it),
        // matching the legacy Curve input. localSize {0,0} also neutralizes
        // the align pivot, exactly like the legacy MeshFactory({0,0}, …).
        cv::Vec2f  localOffset{0.f, 0.f};
        cv::Size2f localSize{0.f, 0.f};
        if (_closed) {
            localOffset = {-minX, -minY};
            localSize = {maxX - minX, maxY - minY};
            for (auto& c : curves) {
                c.p0 += localOffset;
                c.p1 += localOffset;
                c.p2 += localOffset;
            }
        }

        // Use a temporary factory just for step calculation (position doesn't
        // affect quadraticStrokeSteps, so meta.position is irrelevant here).
        MeshFactory sampleFactory(localSize, meta, config);

        // Sample each contour to its own local-space ring.
        std::vector<std::vector<cv::Vec2f>> rings(contourCurves.size());
        if (hasFillNow) {
            for (size_t c = 0; c < contourCurves.size(); ++c) {
                auto [first, count] = contourCurves[c];
                for (size_t k = 0; k < count; ++k) {
                    size_t ci = first + k;
                    int    steps = sampleFactory.quadraticStrokeSteps(curves[ci]);
                    int    sStart = (k == 0) ? 0 : 1;
                    int    sEnd = (_closed && k == count - 1) ? steps - 1 : steps;
                    for (int s = sStart; s <= sEnd; ++s) {
                        float t = static_cast<float>(s) / static_cast<float>(steps);
                        rings[c].push_back(MeshFactory::evalQuadratic(curves[ci], t));
                    }
                }
            }
        }

        // Group rings into outer + holes by winding (letters: 'o' = outline
        // with a hole, 'i' = two independent outers) and triangulate each
        // group with earcut's native hole support. localPoly is the groups'
        // vertices concatenated; earIndices reference it directly, so the
        // solid/2-stop-linear emission below needs no changes.
        std::vector<cv::Vec2f> localPoly;
        std::vector<uint32_t>  earIndices;
        std::vector<cv::Vec2f> boundaryRing;
        std::vector<FillGroup> fillGroups;
        if (hasFillNow && !rings.empty()) {
            auto ringArea = [](const std::vector<cv::Vec2f>& r) {
                double a = 0;
                for (size_t i = 0; i < r.size(); ++i) {
                    const auto& p = r[i];
                    const auto& q = r[(i + 1) % r.size()];
                    a += static_cast<double>(p[0]) * q[1] - static_cast<double>(q[0]) * p[1];
                }
                return a / 2.0;
            };
            auto ringContains = [](const std::vector<cv::Vec2f>& ring, const cv::Vec2f& pt) {
                bool in = false;
                for (size_t i = 0, j = ring.size() - 1; i < ring.size(); j = i++) {
                    if ((ring[i][1] > pt[1]) != (ring[j][1] > pt[1]) &&
                        pt[0] < (ring[j][0] - ring[i][0]) * (pt[1] - ring[i][1]) / (ring[j][1] - ring[i][1]) + ring[i][0])
                        in = !in;
                }
                return in;
            };

            std::vector<double> areas(rings.size());
            size_t              biggest = 0;
            for (size_t i = 0; i < rings.size(); ++i) {
                areas[i] = ringArea(rings[i]);
                if (std::abs(areas[i]) > std::abs(areas[biggest]))
                    biggest = i;
            }
            bool outerSign = areas[biggest] >= 0;
            boundaryRing = rings[biggest];

            std::vector<size_t> outers;
            std::vector<size_t> holes;
            for (size_t i = 0; i < rings.size(); ++i) {
                if (rings[i].size() < 3)
                    continue;
                ((areas[i] >= 0) == outerSign ? outers : holes).push_back(i);
            }

            // Each hole belongs to the smallest outer that contains it; a hole
            // contained by no outer degenerates to its own filled region.
            std::vector<std::vector<size_t>> holesOf(outers.size());
            for (size_t h : holes) {
                ssize_t best = -1;
                for (size_t oi = 0; oi < outers.size(); ++oi) {
                    if (ringContains(rings[outers[oi]], rings[h][0]) &&
                        (best < 0 || std::abs(areas[outers[oi]]) < std::abs(areas[outers[best]])))
                        best = static_cast<ssize_t>(oi);
                }
                if (best >= 0) {
                    holesOf[best].push_back(h);
                } else {
                    outers.push_back(h);
                    holesOf.push_back({});
                }
            }

            for (size_t oi = 0; oi < outers.size(); ++oi) {
                std::vector<std::vector<std::array<float, 2>>> polygon;
                polygon.reserve(1 + holesOf[oi].size());
                uint32_t groupBase = static_cast<uint32_t>(localPoly.size());

                auto addRing = [&](const std::vector<cv::Vec2f>& r) {
                    std::vector<std::array<float, 2>> ring;
                    ring.reserve(r.size());
                    for (const auto& p : r) {
                        ring.push_back({p[0], p[1]});
                        localPoly.push_back(p);
                    }
                    polygon.push_back(std::move(ring));
                };
                addRing(rings[outers[oi]]);
                for (size_t h : holesOf[oi])
                    addRing(rings[h]);

                for (auto v : mapbox::earcut<uint32_t>(polygon))
                    earIndices.push_back(static_cast<uint32_t>(groupBase + v));

                FillGroup group;
                group.outer = rings[outers[oi]];
                group.holes.reserve(holesOf[oi].size());
                for (size_t h : holesOf[oi])
                    group.holes.push_back(rings[h]);
                fillGroups.push_back(std::move(group));
            }
        }

        // Store in cache.
        _geomCache = GeomCache{
            std::move(localPoly),
            std::move(earIndices),
            std::move(curves),
            localSize,
            std::move(contourCurves),
            std::move(boundaryRing),
            std::move(fillGroups),
        };
        _lastGeomHash = geomHash;
        _geomValid = true;
    }

    BP_T(t2);

    // --- Mesh assembly from cached local geometry + current transform ----------
    MeshFactory factory(_geomCache.localSize, meta, config);

    // Apply meta.opacity to all colors, including each gradient stop's alpha.
    float     opacityF = meta.opacity / 255.f;
    cv::Vec4b fillColor = _fillColor;
    cv::Vec4b strokeColor = _strokeColor;
    fillColor[3] = static_cast<uint8_t>(fillColor[3] * opacityF);
    strokeColor[3] = static_cast<uint8_t>(strokeColor[3] * opacityF);

    auto applyOpacity = [opacityF](const std::vector<GradientStop>& stops) {
        std::vector<GradientStop> result = stops;
        for (auto& stop : result)
            stop.color[3] = static_cast<uint8_t>(stop.color[3] * opacityF);
        return result;
    };
    std::vector<GradientStop> fillStops = (_fillGradType != GradType::None) ? applyOpacity(_fillStops) : std::vector<GradientStop>{};
    std::vector<GradientStop> strokeStops = (_strokeGradType != GradType::None) ? applyOpacity(_strokeStops) : std::vector<GradientStop>{};

    bool fillVisible = isTextured() || ((_fillGradType != GradType::None) ? anyStopVisible(fillStops) : fillColor[3] > 0);
    bool strokeVisible = (_strokeGradType != GradType::None) ? anyStopVisible(strokeStops) : strokeColor[3] > 0;
    bool hasStroke = (_strokeWidth > 0.f && strokeVisible);

    // Local mesh-space Y is the negation of world-space Y (world is positive-up,
    // pixel/local space grows downward), so the gradient direction's sine component
    // must be negated to keep the angle convention intuitive in world terms:
    // 0° = left→right, 90° = bottom→top, counterclockwise.
    auto gradientDir = [](float angleDeg) -> cv::Vec2f {
        float angleRad = angleDeg * (static_cast<float>(M_PI) / 180.f);
        return {std::cos(angleRad), -std::sin(angleRad)};
    };

    auto emitStroke = [&](bool insideOnly) {
        for (const auto& [first, count] : _geomCache.contourCurves) {
            if (count == 0)
                continue;
            std::vector<QuadraticBezier2D> contour(
                _geomCache.curves.begin() + static_cast<ssize_t>(first),
                _geomCache.curves.begin() + static_cast<ssize_t>(first + count)
            );
            if (_strokeGradType != GradType::None) {
                cv::Vec2f dir = gradientDir(_strokeGradientAngle);
                factory.addQuadraticStrokePath(
                    contour, _strokeWidth, strokeStops, dir, _closed, insideOnly
                );
            } else {
                factory.addQuadraticStrokePath(
                    contour, _strokeWidth, strokeColor, _closed, insideOnly
                );
            }
        }
    };

    // Open shapes: centered stroke first so fill composites on top if any.
    // Closed shapes: inside stroke drawn after fill (stroke sits on top of fill,
    // outer edge exactly on the shape boundary — no miter spike outside the fill).
    BP_T(t3);
    if (hasStroke && !_closed)
        emitStroke(false);

    // Emit fill vertices (applies current transform M to each local point).
    BP_T(t4);
    const auto& localPoly = _geomCache.localPoly;

    // Radial/conic fills and multi-stop linear strips operate on one ring.
    // Multi-contour shapes use their largest outer ring as that boundary
    // (holes are covered by these fills — documented simplification; solid
    // and 2-stop linear fills respect holes exactly via earcut).
    const auto& boundary = _geomCache.boundaryRing.empty() ? _geomCache.localPoly : _geomCache.boundaryRing;

    if (_fillGradType == GradType::Radial && boundary.size() >= 3 && fillVisible) {
        cv::Vec2f center{_geomCache.localSize.width * 0.5f, _geomCache.localSize.height * 0.5f};

        float maxRadius = 0.f;
        for (const auto& p : boundary) {
            float dx = p[0] - center[0], dy = p[1] - center[1];
            maxRadius = std::max(maxRadius, std::sqrt(dx * dx + dy * dy));
        }
        if (maxRadius < 1e-6f) maxRadius = 1e-6f;

        bool hasHoles = std::any_of(_geomCache.fillGroups.begin(), _geomCache.fillGroups.end(), [](const FillGroup& g) { return !g.holes.empty(); });

        if (hasHoles) {
            // --- Radial gradient on a multi-contour shape with holes (e.g. "O", "g") ---
            //
            // The star mesh below assumes `center` lies inside solid fill, which is
            // false for donut-like glyphs (the gradient center sits in the counter).
            // Instead, triangulate each FillGroup with earcut-with-holes — this
            // naturally excludes hole interiors as geometry — and adaptively
            // subdivide each triangle so its per-vertex color matches
            // lerpGradient(t) smoothly (t is nonlinear in (x,y), so coarse
            // triangles would otherwise show visible faceting).
            auto tFn = [&](cv::Vec2f p) -> float {
                float dx = p[0] - center[0], dy = p[1] - center[1];
                return std::sqrt(dx * dx + dy * dy) / maxRadius;
            };
            auto emit = [&](cv::Vec2f p, cv::Vec4b color) {
                uint32_t idx = factory.vertexCount();
                factory.addVertex(p[0], p[1], color);
                factory.mesh.indices.push_back(idx);
            };
            for (const auto& group : _geomCache.fillGroups)
                for (const auto& tri : triangulateGroup(group))
                    subdivideGradientTriangle(tri[0], tri[1], tri[2], tFn, fillStops, 0, 6, 0.04f, false, emit);
        } else {

            // --- Radial gradient: star mesh (center fan + concentric ring strips) ---
            //
            // Ring vertices are angle-sampled and clamped to the polygon boundary via
            // boundaryDist[j] (ray-cast from center). This keeps every ring — including
            // the outermost — strictly inside (or on) the polygon, so geometry never
            // bleeds outside the shape's silhouette.
            //
            // Clamping the outermost ring to boundaryDist means it sits exactly ON the
            // polygon boundary, but the chord between two adjacent ray samples can still
            // cut inside an actual corner (leaving a black gap there). To fix that without
            // reintroducing bleed, we additionally splice in any boundary vertices
            // ("corner extras") that fall outside the chord for that sector — these are
            // real boundary points, so they can't extend past the shape.

            float        pixelRadius = maxRadius * std::max(meta.scale.x, meta.scale.y);
            int          N = std::max(24, static_cast<int>(2.f * static_cast<float>(M_PI) * pixelRadius / 6.f));
            const float  TAU = 2.f * static_cast<float>(M_PI);
            const size_t M = boundary.size();

            // boundaryDist[j]: distance from center to the polygon boundary along the
            // ray at angle theta_j = TAU*j/N (max intersection with any polygon edge).
            std::vector<float> boundaryDist(N);
            for (int j = 0; j < N; ++j) {
                float     theta = TAU * j / N;
                cv::Vec2f d{std::cos(theta), std::sin(theta)};
                float     best = 0.f;
                for (size_t ei = 0; ei < M; ++ei) {
                    const cv::Vec2f& a = boundary[ei];
                    const cv::Vec2f& b = boundary[(ei + 1) % M];
                    cv::Vec2f        e = b - a;
                    float            denom = d[0] * e[1] - d[1] * e[0];
                    if (std::abs(denom) < 1e-9f) continue;
                    cv::Vec2f ca = a - center;
                    float     t = (ca[0] * e[1] - ca[1] * e[0]) / denom;
                    float     s = (ca[0] * d[1] - ca[1] * d[0]) / denom;
                    if (t > 1e-6f && s >= -1e-6f && s <= 1.f + 1e-6f)
                        best = std::max(best, t);
                }
                boundaryDist[j] = (best > 0.f) ? best : maxRadius;
            }

            auto ringPt = [&](int j, float r) -> cv::Vec2f {
                float theta = TAU * j / N;
                float clampedR = std::min(r, boundaryDist[j]);
                return center + cv::Vec2f{clampedR * std::cos(theta), clampedR * std::sin(theta)};
            };

            auto radialColor = [&](cv::Vec2f pt) -> cv::Vec4b {
                float dx = pt[0] - center[0], dy = pt[1] - center[1];
                return lerpGradient(fillStops, std::sqrt(dx * dx + dy * dy) / maxRadius);
            };

            auto emitRing = [&](float r) {
                for (int j = 0; j < N; ++j) {
                    cv::Vec2f pt = ringPt(j, r);
                    factory.addVertex(pt[0], pt[1], radialColor(pt));
                }
            };

            // Center vertex + ring0 (degenerate to the center point unless the first
            // stop is pinned at a non-zero position).
            uint32_t centerIdx = factory.vertexCount();
            factory.addVertex(center[0], center[1], fillStops.front().color);

            uint32_t ring0Base = factory.vertexCount();
            float    ring0R = fillStops.front().position * maxRadius;
            emitRing(ring0R);

            if (ring0R > 1e-6f) {
                for (int j = 0; j < N; ++j) {
                    factory.mesh.indices.push_back(centerIdx);
                    factory.mesh.indices.push_back(static_cast<uint32_t>(ring0Base + j));
                    factory.mesh.indices.push_back(static_cast<uint32_t>(ring0Base + (j + 1) % N));
                }
            }

            // Pre-emit boundary vertices once — used as "corner extras" when
            // triangulating the outermost ring strip.
            uint32_t polyBase = factory.vertexCount();
            for (const auto& p : boundary)
                factory.addVertex(p[0], p[1], radialColor(p));

            std::vector<float> pAngle(M), pDist(M);
            for (size_t i = 0; i < M; ++i) {
                float dx = boundary[i][0] - center[0], dy = boundary[i][1] - center[1];
                float a = std::atan2(dy, dx);
                pAngle[i] = (a < 0.f) ? a + TAU : a;
                pDist[i] = std::sqrt(dx * dx + dy * dy);
            }
            std::vector<std::vector<size_t>> sectorVerts(N);
            for (size_t i = 0; i < M; ++i) {
                int sec = static_cast<int>(pAngle[i] * N / TAU);
                sec = std::clamp(sec, 0, N - 1);
                sectorVerts[sec].push_back(i);
            }
            for (auto& sv : sectorVerts)
                std::sort(sv.begin(), sv.end(), [&](size_t a, size_t b) { return pAngle[a] < pAngle[b]; });

            // Ring-to-ring quad strips for each stop interval; the last interval also
            // splices in corner extras.
            uint32_t prevBase = ring0Base;
            for (size_t k = 0; k + 1 < fillStops.size(); ++k) {
                float rA = fillStops[k].position * maxRadius;
                float rB = fillStops[k + 1].position * maxRadius;
                if (rB <= rA + 1e-6f) continue;

                uint32_t outerBase = factory.vertexCount();
                emitRing(rB);

                bool isLast = (k + 2 == fillStops.size());

                for (int j = 0; j < N; ++j) {
                    int      jn = (j + 1) % N;
                    uint32_t i0 = static_cast<uint32_t>(prevBase + j);
                    uint32_t i1 = static_cast<uint32_t>(prevBase + jn);
                    uint32_t i2 = static_cast<uint32_t>(outerBase + j);
                    uint32_t i3 = static_cast<uint32_t>(outerBase + jn);

                    factory.mesh.indices.push_back(i0);
                    factory.mesh.indices.push_back(i1);
                    factory.mesh.indices.push_back(i2);

                    if (isLast) {
                        float ringRJ = std::min(rB, boundaryDist[j]);
                        float ringRJn = std::min(rB, boundaryDist[jn]);
                        float thresh = std::max(ringRJ, ringRJn);

                        // Fan from i1 through the outer chain (i3, extras…, i2), where
                        // extras are boundary vertices in this sector that lie outside
                        // the i3–i2 chord.
                        uint32_t    prev = i3;
                        const auto& extras = sectorVerts[j];
                        for (auto it = extras.rbegin(); it != extras.rend(); ++it) {
                            size_t pi = *it;
                            if (pDist[pi] <= thresh + 1e-4f) continue;
                            uint32_t e = static_cast<uint32_t>(polyBase + pi);
                            factory.mesh.indices.push_back(i1);
                            factory.mesh.indices.push_back(prev);
                            factory.mesh.indices.push_back(e);
                            prev = e;
                        }
                        factory.mesh.indices.push_back(i1);
                        factory.mesh.indices.push_back(prev);
                        factory.mesh.indices.push_back(i2);
                    } else {
                        factory.mesh.indices.push_back(i1);
                        factory.mesh.indices.push_back(i3);
                        factory.mesh.indices.push_back(i2);
                    }
                }
                prevBase = outerBase;
            }

        } // end !hasHoles

    } else if (_fillGradType == GradType::Conic && boundary.size() >= 3 && fillVisible) {
        // --- Conic gradient: fan from center to the polygon boundary ---
        //
        // Color depends only on the angle around `center`, wrapped to t∈[0,1).
        // A hard "seam" is inserted at `_fillGradientAngle` (t=0 meets t=1) —
        // matching CSS conic-gradient when the first/last stop colors differ.
        //
        // Each pie-slice triangle gets its own center-vertex copy, colored to
        // match its leading edge. A single shared center vertex would blend
        // every slice toward one fixed color near the middle, creating spurious
        // "spokes" — color must stay constant along any radius.

        cv::Vec2f center{_geomCache.localSize.width * 0.5f, _geomCache.localSize.height * 0.5f};

        float maxRadius = 0.f;
        for (const auto& p : boundary) {
            float dx = p[0] - center[0], dy = p[1] - center[1];
            maxRadius = std::max(maxRadius, std::sqrt(dx * dx + dy * dy));
        }
        if (maxRadius < 1e-6f) maxRadius = 1e-6f;

        const float TAU = 2.f * static_cast<float>(M_PI);

        // World-space sweep angle: 0 = right, 90 = up, CCW (matches LinearGradient's
        // angle convention). Local space Y is flipped relative to world space, so
        // local angle = -world angle.
        float angleRad = _fillGradientAngle * (static_cast<float>(M_PI) / 180.f);

        auto wrapToUnit = [](float x) {
            x = std::fmod(x, 1.f);
            return (x < 0.f) ? x + 1.f : x;
        };
        auto conicT = [&](float localAngle) {
            return wrapToUnit((-localAngle - angleRad) / TAU);
        };

        bool hasHoles = std::any_of(_geomCache.fillGroups.begin(), _geomCache.fillGroups.end(), [](const FillGroup& g) { return !g.holes.empty(); });

        if (hasHoles) {
            // --- Conic gradient on a multi-contour shape with holes (e.g. "O", "g") ---
            //
            // Same rationale as the radial hasHoles branch: triangulate each
            // FillGroup with earcut-with-holes (excludes hole interiors), then
            // adaptively subdivide each triangle so its per-vertex color matches
            // lerpGradient(conicT(angle)) smoothly. conicT wraps at 1->0, so
            // subdivision termination uses a wrap-aware delta (wrapT=true).
            auto tFn = [&](cv::Vec2f p) -> float {
                float dx = p[0] - center[0], dy = p[1] - center[1];
                return conicT(std::atan2(dy, dx));
            };
            auto emit = [&](cv::Vec2f p, cv::Vec4b color) {
                uint32_t idx = factory.vertexCount();
                factory.addVertex(p[0], p[1], color);
                factory.mesh.indices.push_back(idx);
            };
            for (const auto& group : _geomCache.fillGroups)
                for (const auto& tri : triangulateGroup(group))
                    subdivideGradientTriangle(tri[0], tri[1], tri[2], tFn, fillStops, 0, 6, 0.04f, true, emit);
        } else {

            float        pixelRadius = maxRadius * std::max(meta.scale.x, meta.scale.y);
            int          N = std::max(24, static_cast<int>(2.f * static_cast<float>(M_PI) * pixelRadius / 6.f));
            const size_t M = boundary.size();

            // Ray-cast from center at local angle `theta` to the polygon boundary.
            auto rayDist = [&](float theta) -> float {
                cv::Vec2f d{std::cos(theta), std::sin(theta)};
                float     best = 0.f;
                for (size_t ei = 0; ei < M; ++ei) {
                    const cv::Vec2f& a = boundary[ei];
                    const cv::Vec2f& b = boundary[(ei + 1) % M];
                    cv::Vec2f        e = b - a;
                    float            denom = d[0] * e[1] - d[1] * e[0];
                    if (std::abs(denom) < 1e-9f) continue;
                    cv::Vec2f ca = a - center;
                    float     t = (ca[0] * e[1] - ca[1] * e[0]) / denom;
                    float     s = (ca[0] * d[1] - ca[1] * d[0]) / denom;
                    if (t > 1e-6f && s >= -1e-6f && s <= 1.f + 1e-6f)
                        best = std::max(best, t);
                }
                return (best > 0.f) ? best : maxRadius;
            };

            // Boundary chain: N evenly-spaced ray samples + any boundary vertices
            // that stick out beyond their sector's chord (corner extras), sorted by
            // local angle — same corner-coverage idea as the radial gradient's
            // outermost ring.
            struct ChainPt
            {
                cv::Vec2f pt;
                float     angle;
            };

            std::vector<ChainPt> chain;
            chain.reserve(N + M);

            std::vector<float> boundaryDist(N);
            for (int j = 0; j < N; ++j) {
                float theta = TAU * j / N;
                boundaryDist[j] = rayDist(theta);
                chain.push_back({center + cv::Vec2f{boundaryDist[j] * std::cos(theta), boundaryDist[j] * std::sin(theta)}, theta});
            }
            for (size_t i = 0; i < M; ++i) {
                float dx = boundary[i][0] - center[0], dy = boundary[i][1] - center[1];
                float a = std::atan2(dy, dx);
                if (a < 0.f) a += TAU;
                float dist = std::sqrt(dx * dx + dy * dy);
                int   j = std::clamp(static_cast<int>(a * N / TAU), 0, N - 1);
                int   jn = (j + 1) % N;
                if (dist > std::max(boundaryDist[j], boundaryDist[jn]) + 1e-4f)
                    chain.push_back({boundary[i], a});
            }
            std::sort(chain.begin(), chain.end(), [](const ChainPt& a, const ChainPt& b) { return a.angle < b.angle; });

            // Insert a hard seam at the gradient's start angle: two coincident
            // vertices, t=0 (first stop color) just before, t=1 (last stop color)
            // just after, in angular order.
            float la0 = std::fmod(-angleRad, TAU);
            if (la0 < 0.f) la0 += TAU;
            float     seamR = rayDist(la0);
            cv::Vec2f seamPt = center + cv::Vec2f{seamR * std::cos(la0), seamR * std::sin(la0)};

            size_t insertAt = chain.size();
            for (size_t i = 0; i < chain.size(); ++i) {
                if (chain[i].angle > la0) {
                    insertAt = i;
                    break;
                }
            }
            chain.insert(chain.begin() + static_cast<long>(insertAt), 2, ChainPt{seamPt, la0});

            std::vector<uint32_t>  chainIdx(chain.size());
            std::vector<cv::Vec4b> chainColor(chain.size());
            for (size_t i = 0; i < chain.size(); ++i) {
                if (i == insertAt)
                    chainColor[i] = lerpGradient(fillStops, 0.f);
                else if (i == insertAt + 1)
                    chainColor[i] = lerpGradient(fillStops, 1.f);
                else
                    chainColor[i] = lerpGradient(fillStops, conicT(chain[i].angle));
                chainIdx[i] = factory.vertexCount();
                factory.addVertex(chain[i].pt[0], chain[i].pt[1], chainColor[i]);
            }

            size_t cnt = chain.size();
            for (size_t i = 0; i < cnt; ++i) {
                uint32_t c = factory.vertexCount();
                factory.addVertex(center[0], center[1], chainColor[i]);
                factory.mesh.indices.push_back(c);
                factory.mesh.indices.push_back(chainIdx[i]);
                factory.mesh.indices.push_back(chainIdx[(i + 1) % cnt]);
            }

        } // end !hasHoles

    } else if (fillVisible && !_geomCache.earIndices.empty()) {
        // --- Linear gradient or solid fill: earcut-based ---
        uint32_t firstPolyIdx = factory.vertexCount();

        if (_fillGradType == GradType::Linear) {
            cv::Vec2f dir = gradientDir(_fillGradientAngle);

            float minProj = std::numeric_limits<float>::max();
            float maxProj = std::numeric_limits<float>::lowest();
            for (const auto& p : localPoly) {
                float proj = p[0] * dir[0] + p[1] * dir[1];
                minProj = std::min(minProj, proj);
                maxProj = std::max(maxProj, proj);
            }
            float range = maxProj - minProj;

            if (fillStops.size() <= 2) {
                // 2-stop: color is a linear function of projection → the earcut
                // fan triangulation reproduces it exactly via GPU linear interp.
                for (const auto& p : localPoly) {
                    float proj = p[0] * dir[0] + p[1] * dir[1];
                    float t = (range > 0.f) ? (proj - minProj) / range : 0.f;
                    factory.addVertex(p[0], p[1], lerpGradient(fillStops, t));
                }
                for (auto idx : _geomCache.earIndices)
                    factory.mesh.indices.push_back(firstPolyIdx + idx);
            } else {
                // Multi-stop: clip each fill group (outer ring + its holes) to each
                // stop interval, then earcut-with-holes per clipped strip — so holes
                // (e.g. the counter of a letter "O") are respected, unlike the
                // radial/conic fills which still use a single boundary ring.
                for (size_t k = 0; k + 1 < fillStops.size(); ++k) {
                    float projA = minProj + fillStops[k].position * range;
                    float projB = minProj + fillStops[k + 1].position * range;
                    if (projA >= projB) continue;

                    for (const auto& group : _geomCache.fillGroups) {
                        auto outerStrip = clipPolyHalfPlane(group.outer, dir, projA, true);
                        outerStrip = clipPolyHalfPlane(outerStrip, dir, projB, false);
                        if (outerStrip.size() < 3) continue;

                        std::vector<std::vector<std::array<float, 2>>> stripPoly;
                        stripPoly.reserve(1 + group.holes.size());
                        stripPoly.push_back({});
                        stripPoly[0].reserve(outerStrip.size());
                        for (const auto& p : outerStrip)
                            stripPoly[0].push_back({p[0], p[1]});

                        for (const auto& hole : group.holes) {
                            auto holeStrip = clipPolyHalfPlane(hole, dir, projA, true);
                            holeStrip = clipPolyHalfPlane(holeStrip, dir, projB, false);
                            if (holeStrip.size() < 3) continue;
                            std::vector<std::array<float, 2>> ring;
                            ring.reserve(holeStrip.size());
                            for (const auto& p : holeStrip)
                                ring.push_back({p[0], p[1]});
                            stripPoly.push_back(std::move(ring));
                        }

                        auto stripIdx = mapbox::earcut<uint32_t>(stripPoly);

                        uint32_t stripBase = factory.vertexCount();
                        for (const auto& ring : stripPoly) {
                            for (const auto& p : ring) {
                                float proj = p[0] * dir[0] + p[1] * dir[1];
                                float localT = (proj - projA) / (projB - projA);
                                factory.addVertex(p[0], p[1], lerpColor(fillStops[k].color, fillStops[k + 1].color, localT));
                            }
                        }
                        for (auto idx : stripIdx)
                            factory.mesh.indices.push_back(stripBase + idx);
                    }
                }
            }
        } else if (isTextured()) {
            float w = _geomCache.localSize.width;
            float h = _geomCache.localSize.height;

            if (_uvMapping == UVMapping::Stretch || w <= 0.f || h <= 0.f) {
                // Stretch (default): bbox-normalized UVs.
                for (const auto& p : localPoly) {
                    float u = (w > 0.f) ? p[0] / w : 0.f;
                    float v = (h > 0.f) ? p[1] / h : 0.f;
                    factory.addVertex(p[0], p[1], u, v, opacityF);
                }
            } else {
                // Radial/conic: polar UVs around the bbox center, matching
                // GradType::Radial/Conic's center+angle convention (local angle
                // = -world angle, since local Y is flipped relative to world).
                cv::Vec2f   center{w * 0.5f, h * 0.5f};
                float       maxRadius = std::sqrt(center[0] * center[0] + center[1] * center[1]);
                const float TAU = 2.f * static_cast<float>(M_PI);
                float       angleRad = _uvAngle * (static_cast<float>(M_PI) / 180.f);

                auto wrapToUnit = [](float x) {
                    x = std::fmod(x, 1.f);
                    return (x < 0.f) ? x + 1.f : x;
                };

                for (const auto& p : localPoly) {
                    float dx = p[0] - center[0], dy = p[1] - center[1];
                    float r = std::min(std::sqrt(dx * dx + dy * dy) / maxRadius, 1.f);
                    float theta = wrapToUnit((-std::atan2(dy, dx) - angleRad) / TAU);
                    float u, v;
                    if (_uvMapping == UVMapping::Radial) {
                        u = r;
                        v = theta;
                    } else { // Conic
                        u = theta;
                        v = r;
                    }
                    factory.addVertex(p[0], p[1], u, v, opacityF);
                }
            }
            for (auto idx : _geomCache.earIndices)
                factory.mesh.indices.push_back(firstPolyIdx + idx);
        } else {
            // Solid fill.
            for (const auto& p : localPoly)
                factory.addVertex(p[0], p[1], fillColor);
            for (auto idx : _geomCache.earIndices)
                factory.mesh.indices.push_back(firstPolyIdx + idx);
        }
    }

    // Closed shapes: inside stroke drawn last so it sits on top of fill,
    // outer edge on the shape boundary, inner edge inset by strokeWidth.
    if (hasStroke && _closed)
        emitStroke(true);

    BP_T(t5);

    if (BP_US(t0, t5) > 400)
        VC_LOG(std::format("[bezier] buildPath:{}µs  geom:{}µs  factory:{}µs  stroke:{}µs  fill:{}µs  pts:{}\n", BP_US(t0, t1), BP_US(t1, t2), BP_US(t2, t3), BP_US(t3, t4), BP_US(t4, t5), n));

    Mesh result = factory.generateMesh();

    if (isTextured()) {
        result.hasTexture = true;
        result.textureDescriptor = textureDescriptor();
    }

    _meshCache = result;
    _lastMeshHash = meshHash;
    _lastShapeHash = shapeHash;
    _meshCacheValid = true;
    _meshCachePosition = {meta.position.x, meta.position.y};
    _meshCacheScale = {meta.scale.x, meta.scale.y};
    _meshCacheRotation = meta.rotation;
    _meshCacheAlign = {meta.align.x, meta.align.y};
    _meshCacheOpacity = meta.opacity;
    _meshCacheScreen = {config.screenWidth, config.screenHeight};

    return result;
}
