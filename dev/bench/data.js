window.BENCHMARK_DATA = {
  "lastUpdate": 1792710379763,
  "repoUrl": "https://github.com/anpawo/video-code",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "hippolytelefer@gmail.com",
            "name": "Hip-po",
            "username": "Hip-po"
          },
          "committer": {
            "email": "hippolytelefer@gmail.com",
            "name": "Hip-po",
            "username": "Hip-po"
          },
          "distinct": false,
          "id": "d45262a6932075a1842b3420bb6bfba78e83431e",
          "message": "fix: update regex for whitespace trimming and ensure compatibility with Qt's engine",
          "timestamp": "2026-09-28T00:28:10+02:00",
          "tree_id": "2046aaa84c1f63079b84ea88bd8f692df5cee29e",
          "url": "https://github.com/anpawo/Video-Code/commit/d45262a6932075a1842b3420bb6bfba78e83431e"
        },
        "date": 1790552940652,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "a3cb0394c1361c68f174ad18b09a8ed074b5dec3",
          "message": "gitignore: a video's footage stays out of the repository\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T11:59:18+02:00",
          "tree_id": "238ddff272721563984f53273c0dddb00d64169e",
          "url": "https://github.com/anpawo/Video-Code/commit/a3cb0394c1361c68f174ad18b09a8ed074b5dec3"
        },
        "date": 1790589647841,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "ff23a73ef254efb9d8e9bf8dd3bdc35005ac66f6",
          "message": "board: rows keep their GitHub issue in step, landed rows leave\n\ndocs/board_issues.py gives a new row its issue and closes the issue of a row\nwhose fix is on main or that moved to Won't do. The LoL template, the ⌘1..4\nmenus and the timeline span landed; the black preview after a layout switch\njoins To do.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T12:01:12+02:00",
          "tree_id": "f557b6e4e35a385ac89897a200605d71f5bb1664",
          "url": "https://github.com/anpawo/Video-Code/commit/ff23a73ef254efb9d8e9bf8dd3bdc35005ac66f6"
        },
        "date": 1790590049200,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "bc4e93bf673f6c1bc58c201745d728295317b173",
          "message": "preview: a layout switch no longer blacks out the clips\n\nA new pane size rebuilds the preview renderer, and every clip's texture lived\nin the one thrown away — only inputs rebuilt by the last run were uploaded\nagain, so the pane went flat until the scene ran again. A splitter drag did\nthe same. Every Image and Video is now queued again for the new renderer.\n\ntest/editor_preview_resize_test.py takes a frame, presses ⌘4, takes another:\nflat without this, the clip with it.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T12:18:08+02:00",
          "tree_id": "abadc08b82beff6c616cae028ffc0435c37d55fd",
          "url": "https://github.com/anpawo/Video-Code/commit/bc4e93bf673f6c1bc58c201745d728295317b173"
        },
        "date": 1790590794314,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "9e4429615fbf1e416a4e376484fa70009a958f48",
          "message": "board: the black preview after a layout switch landed (bc4e93b)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T12:18:34+02:00",
          "tree_id": "e7e605c28eb867d15e8686e1a1da2b2221c42fc7",
          "url": "https://github.com/anpawo/Video-Code/commit/9e4429615fbf1e416a4e376484fa70009a958f48"
        },
        "date": 1790591191437,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "ced60e7f4e361c36e62502d77fa69fae6a3c466d",
          "message": "board: the renderer crash, frame hold, LoL hook and agent's changed lines landed\n\nThe crash (#77) leaves the board; the three features stay under Needs your\ncheck with their commits, for an eye or a mouse. fadeIn's hidden and\nwaitFor(clip.end) were on main and asked only a go: they leave too. The\nREADME gif joins the checks.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T18:13:32+02:00",
          "tree_id": "6456b3c351b9d79226e9cf479a2a69bc0b92d189",
          "url": "https://github.com/anpawo/Video-Code/commit/ced60e7f4e361c36e62502d77fa69fae6a3c466d"
        },
        "date": 1790612137627,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "d5e4d8f1f60e11579f66bc9218b40b87124872f2",
          "message": "board: --lint in progress; our own viewer noted as a to-do (79)\n\nPreview does not play a GIF, which is how the idea came up. What only a\nviewer of ours would do — a render next to its golden, the scene lines behind\nthe frame, delivery checks — is in FEATURES_TODO I. Not urgent.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T18:42:26+02:00",
          "tree_id": "d78d521162121fa1777000ba1d2e39a1fc994e8b",
          "url": "https://github.com/anpawo/Video-Code/commit/d5e4d8f1f60e11579f66bc9218b40b87124872f2"
        },
        "date": 1790613877343,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "43266ed37cb87042811bfacb40727b8c482fb5d1",
          "message": "Revert \"probe: a click moves on the spot between press and release\"\n\nThis reverts commit 181eaad. On the Linux runner it fixed neither of\ntimeline_drag's two Click: checks and broke four more: CI went from 2 failures\n(run 36408958368) to 6 (run 36449531410) — the release now writes an edit, so\nthe move turns the click into a drag there. The commit's claim that the clicks\npass came from a debug run, not the full suite. Row 68 stays in progress.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T18:44:27+02:00",
          "tree_id": "dfac083e091f11b9c95977202bc08046a28be821",
          "url": "https://github.com/anpawo/Video-Code/commit/43266ed37cb87042811bfacb40727b8c482fb5d1"
        },
        "date": 1790614433340,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "c63ba697828435e11d2ab4dbf14a9632977b2f28",
          "message": "board: --lint landed, to be seen in the editor; the stale backdated-write warning noted (80)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T19:30:37+02:00",
          "tree_id": "e90d8d1a71c780646f9e5397fbfa5af39af2b1ba",
          "url": "https://github.com/anpawo/Video-Code/commit/c63ba697828435e11d2ab4dbf14a9632977b2f28"
        },
        "date": 1790616740870,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "8b97dd950a3261953858dcea1b98a4334d3a1bfc",
          "message": "board: row 79 narrowed to what no viewer does, after the research\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T19:33:50+02:00",
          "tree_id": "eebe7e054d98286468255ec1852bee99be14f685",
          "url": "https://github.com/anpawo/Video-Code/commit/8b97dd950a3261953858dcea1b98a4334d3a1bfc"
        },
        "date": 1790617138999,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "01d1fe128d484a01154dfbfd1ce8caf4fc7fc61f",
          "message": "board: our own viewer won't be built — the preview already is one, and IINA plays GIFs\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-09-28T19:55:09+02:00",
          "tree_id": "11034715d1ed5f760e43aec87d303aa93436ff30",
          "url": "https://github.com/anpawo/Video-Code/commit/01d1fe128d484a01154dfbfd1ce8caf4fc7fc61f"
        },
        "date": 1790618257060,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "hippolytelefer@gmail.com",
            "name": "Hippolyte lefer",
            "username": "Hip-po"
          },
          "committer": {
            "email": "hippolytelefer@gmail.com",
            "name": "Hippolyte lefer",
            "username": "Hip-po"
          },
          "distinct": false,
          "id": "092d44075d852728e7908a37b16d75a160a08838",
          "message": "board: 43 checks, not 46 (81)",
          "timestamp": "2026-09-29T01:55:21+02:00",
          "tree_id": "0b12815420e51f7262ca8ba218ce35a8b4b8f674",
          "url": "https://github.com/anpawo/Video-Code/commit/092d44075d852728e7908a37b16d75a160a08838"
        },
        "date": 1790640895207,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "112256146+anpawo@users.noreply.github.com",
            "name": "anpawo",
            "username": "anpawo"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b39f4eb96152f230d16b80dd6ef4e81edd62c4fd",
          "message": "Merge pull request #380 from anpawo/fix/345-linux-ci\n\nci: green again — av stays below 19, and a click's release is built after its press",
          "timestamp": "2026-10-06T14:16:02+02:00",
          "tree_id": "d50b9308465d97042bbefcb9e6cb64fc40b95993",
          "url": "https://github.com/anpawo/video-code/commit/b39f4eb96152f230d16b80dd6ef4e81edd62c4fd"
        },
        "date": 1791289071031,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "112256146+anpawo@users.noreply.github.com",
            "name": "anpawo",
            "username": "anpawo"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "37cf335e27cc8514593701f380c17cec4ad98cd1",
          "message": "Merge pull request #382 from anpawo/ci/381-macos-gate-remember-on-prs\n\nci: the macOS build is a gate, and remember runs on pull requests",
          "timestamp": "2026-10-06T15:12:32+02:00",
          "tree_id": "ab09a74061c6e974626042f95cacc3f37faa3d60",
          "url": "https://github.com/anpawo/video-code/commit/37cf335e27cc8514593701f380c17cec4ad98cd1"
        },
        "date": 1791292453523,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "112256146+anpawo@users.noreply.github.com",
            "name": "anpawo",
            "username": "anpawo"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "ac080a471222d7933fd1ef1267b3f4376cc8adda",
          "message": "Merge pull request #377 from anpawo/claude/audit-runedata\n\naudit: league/runes.py drops its unused RuneData class",
          "timestamp": "2026-10-06T15:31:58+02:00",
          "tree_id": "a1bf4266d2ce5c1750b1d56b14c660d279070589",
          "url": "https://github.com/anpawo/video-code/commit/ac080a471222d7933fd1ef1267b3f4376cc8adda"
        },
        "date": 1791293601334,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "112256146+anpawo@users.noreply.github.com",
            "name": "anpawo",
            "username": "anpawo"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "75df963e76b52a48cbe3b8a9826990fcbcecf0e2",
          "message": "Merge pull request #378 from anpawo/claude/audit-dead-box\n\naudit: template/input/Box.py, orphaned and broken, leaves",
          "timestamp": "2026-10-06T15:48:26+02:00",
          "tree_id": "30d992662adbc1045d6ab5dd455a8f4c2bcfd0bc",
          "url": "https://github.com/anpawo/video-code/commit/75df963e76b52a48cbe3b8a9826990fcbcecf0e2"
        },
        "date": 1791294609408,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "82a5baa9294a61123a2b07986c3a958d254650af",
          "message": "library: the rune page, seventeen parts and the page they make (#383)\n\nThe rune video drafted in HyperFrames on 3 Oct. was split into its 17 parts\nso that each could become a template here. They are videocode/template/input/\nRunePage.py, one class each with its own entrance, and the Library's search\nfinds every one by a word of its first docstring line. videos/lol/runes.py\nlays a page out of them from data; locke_runes.py is the original video's\npage. Against the HyperFrames render, over the 300 frames: SSIM 0.977.\ndocs/by-example/features/rune_page.py shows one of each, the repository's\nlogo standing in for the art, which is the game's and is not committed.\n\nCinzel Bold is bundled beside Inter (OFL, its licence beside it): the page's\nserif, cut at weight 700 from the variable font.\n\nA passed-over option fades to 120 where the original fades to 22 %: under a\nfragment shader the opacity lands twice, measured on one icon.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01CRwF75JEc7uUkhpaiT6gbo",
          "timestamp": "2026-10-12T01:24:53+02:00",
          "tree_id": "59142a7f123185d23396657c6b1f9e541f338c57",
          "url": "https://github.com/anpawo/video-code/commit/82a5baa9294a61123a2b07986c3a958d254650af"
        },
        "date": 1791761385504,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "918f4d4c79ad19ee925bf79562a2a9d316a99c34",
          "message": "errors: the project log opens on the clock a template starts from (#383)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01CRwF75JEc7uUkhpaiT6gbo",
          "timestamp": "2026-10-12T01:30:07+02:00",
          "tree_id": "5c8a59dd307c17b8631334e0427cabb5889b18c4",
          "url": "https://github.com/anpawo/video-code/commit/918f4d4c79ad19ee925bf79562a2a9d316a99c34"
        },
        "date": 1791761954186,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "c8b9e87876c32caf5ea1540a247cdc40188edd13",
          "message": "library: Hemicycle, a parliament's seats and a vote lit as a wave (#386)\n\nThe picture a vote explainer is built on: every deputy a seat on a half-ring\ncut by aisles, the groups seated left to right as slices, and a group's seats\ncoming on in green or red from its own side of the chamber. A row holds seats\nin proportion to its radius, rounded by largest remainder so the rows add up\nto the chamber exactly; a seat is narrower only where its row's rounding\nleaves it less room. light() takes the number who voted, clear() puts the\nlights back. Manim has no seat chart: its nearest tools are a VGroup of dots\nand LaggedStart.\n\nvideos/politics/assembly.py is the first scene on it, in portrait: a label\npops under the card's corner and the group's seats follow, twice. Its two\nsounds are written out as waves by videos/politics/sfx.py (a pop falling from\n750 to 320 Hz, a rising trill of ticks 20 ms apart), from shapes measured on\na reference Reel, so they end on a decay and are nobody else's recording.\n--set sounds=reel plays the clips cut from that Reel instead; those are not\ncommitted.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01ThWboS6RvmepFrsMFPJ1fU",
          "timestamp": "2026-10-13T12:52:43+02:00",
          "tree_id": "1a4ac53edc757820ffb470d508b78ec1b06ff990",
          "url": "https://github.com/anpawo/video-code/commit/c8b9e87876c32caf5ea1540a247cdc40188edd13"
        },
        "date": 1791888990842,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "e48551680a0b69adee9bccd591fca881b6904d14",
          "message": "errors: an effect keeps its own clock, apply's start does not move it (#386)\n\nWritten the day it happened: the hemicycle scene's label popped at second 0,\nhidden, and came on whole at its cue. The stills taken after the entrance\nlooked right; the width measured frame by frame did not.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01ThWboS6RvmepFrsMFPJ1fU",
          "timestamp": "2026-10-13T13:01:50+02:00",
          "tree_id": "031b9aa8ec12dba792d33c5f5c70b902ec5266c9",
          "url": "https://github.com/anpawo/video-code/commit/e48551680a0b69adee9bccd591fca881b6904d14"
        },
        "date": 1791889620284,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "56f8406b5f18c88ba09a7eaf39e567ded1b7699b",
          "message": "board: the French rows wait as a to-do of their own (91, #388)\n\nAbout thirty rows of the board, the page's headings and most of the long\nrecord predate the English rule of 27 Sept. Asked on 13 Oct. to park it as a\nto-do rather than translate it in passing.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01ThWboS6RvmepFrsMFPJ1fU",
          "timestamp": "2026-10-13T14:47:35+02:00",
          "tree_id": "860f85fbc0a1b0d4fbffa5b0b1ebd1601addd904",
          "url": "https://github.com/anpawo/video-code/commit/56f8406b5f18c88ba09a7eaf39e567ded1b7699b"
        },
        "date": 1791895764790,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "91091565+Hip-po@users.noreply.github.com",
            "name": "hip-po",
            "username": "Hip-po"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "61235e6c4127af2e535ecde187145eaae1cef445",
          "message": "Merge pull request #390 from anpawo/feature/389-agent-resume\n\nagent: the conversation survives closing the editor (#389)",
          "timestamp": "2026-10-15T14:21:46+02:00",
          "tree_id": "49009c7e90a7da5175aa76d496e5f904228a85ae",
          "url": "https://github.com/anpawo/video-code/commit/61235e6c4127af2e535ecde187145eaae1cef445"
        },
        "date": 1792067037325,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "6681801fa22d474497ebb45dce91e72ed15731b9",
          "message": "templates: one clip on the timeline, their values in the Inspector (#393)\n\n`tutorial(...)` written once in scene.py makes the whole video from lines of\nvideos/lol/tutorial.py, and the timeline drew those lines — Video ×8,\nText ×129, ×191, ×46 — while the one line the scene wrote was nowhere. The\nInspector then read each of those rows against a line of scene.py with the\nsame number.\n\nA template is now any function or class of another file of the project that\nthe scene calls. Each input it makes records the scene's call: the line, the\nname it called, and where the callable lives (\"videos.lol.tutorial:tutorial\"),\nfound by walking out to the scene file's frame. Only inputs made outside the\nscene file are walked, so a scene that makes its own pays one comparison per\ninput, and a render pays nothing: only the editor's run names the scene file.\n\n- The timeline draws one clip per call, named like any element (the variable\n  on its line, else the template's name), in a hue of its own, spanning all it\n  made. Its rows are its members.\n- The Inspector, and the card, show the template's own parameters, read off\n  the call and written back to it — by position where the call has them so.\n  A value written over several lines reads as one line and is edited in the\n  code. Library templates (BarChart, Hemicycle), which the scene imports from\n  their module, now answer too: their class is looked for there.\n- The Inspector's \"Timeline · parts\" row shows the rows under the clip again,\n  for the session, without running the scene.\n- A drag on a template's clip is refused, said: a `.wait()` or a `hide`\n  written on a call that returns nothing would break the scene.\n\nA function default is now written by its name (`clipTransition=whipPan`), and\n`str | None` reads as an optional str.\n\ntest/template_fold_test.py drives a windowless editor over two calls of a\ntemplate beside the scene, and also checks the zoom of #392 and the code pane\nof #391; it fails on both before their commits. 94 test files, 54 scenes\nunchanged.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T14:28:52+02:00",
          "tree_id": "6ed869b4e737847367d530c34bfcf423f38d606b",
          "url": "https://github.com/anpawo/video-code/commit/6681801fa22d474497ebb45dce91e72ed15731b9"
        },
        "date": 1792067646172,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "c57840f60d5dc67fa55a2fbee40b73a264e2b4f9",
          "message": "errors: QML's engine has no flatMap (#393)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T14:34:53+02:00",
          "tree_id": "fd6c38df19939d3e1fe704c36727f50086dbc611",
          "url": "https://github.com/anpawo/video-code/commit/c57840f60d5dc67fa55a2fbee40b73a264e2b4f9"
        },
        "date": 1792068189132,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "91091565+Hip-po@users.noreply.github.com",
            "name": "hip-po",
            "username": "Hip-po"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "78cce087aa87f4d6b08b3253bd0e22e68cb5896e",
          "message": "Merge pull request #395 from anpawo/feature/394-agent-model-effort\n\nagent: the model and the effort, picked under the field (#394)",
          "timestamp": "2026-10-15T14:50:27+02:00",
          "tree_id": "2d6dccd388c282cfae8fa62fd5006c43d96d20bb",
          "url": "https://github.com/anpawo/video-code/commit/78cce087aa87f4d6b08b3253bd0e22e68cb5896e"
        },
        "date": 1792068783955,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "2cacfcfd33c3b66001986beae12de3438cd32a3c",
          "message": "preview: a mesh kept across a new renderer takes the new texture (#396)\n\n⌘3 with the editor open killed it with SIGSEGV in vkQueueSubmit, under\nEditor::renderFrame: MoltenVK bound a descriptor set that no longer existed.\n\nA layout switch resizes the Preview, and a new size rebuilds its renderer:\nthe old one's textures are destroyed and every Image/Video is uploaded again,\nunder new sets. Two caches kept the old ones: the scene's meshes of the last\nframe drawn, returned as they were when the frame index has not moved, and\neach shape's own mesh, whose hash leaves the texture out. It went unseen\nwhile the new sets landed at the old addresses, in the same order — which\nthey do until a run rebuilds one clip and its texture is uploaded after the\nothers. Then the switch bound a freed set: the windowless preview went black\nand stayed black, the editor with a window died.\n\nThe scene's cache is dropped with the renderer, and a shape's cached mesh\ntakes the texture it holds now.\n\ntest/editor_preview_resize_test.py now shrinks the clip, runs, and switches\nto Vibe Editing at the same frame: the pane read flat black without this\n(spread 0.0), the clip with it (67.5). 95 test files, 54 scenes unchanged.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T14:54:46+02:00",
          "tree_id": "8c1de3ab1493a08a1c7732c63982d1fe7647c8ba",
          "url": "https://github.com/anpawo/video-code/commit/2cacfcfd33c3b66001986beae12de3438cd32a3c"
        },
        "date": 1792069380361,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "644a4125a9b493362d95bec257dc982c225b6a5e",
          "message": "board: templates back in progress, as a block with nested ones inside (93, #398)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T15:07:15+02:00",
          "tree_id": "57b3fd416628b6244f377d49f34d1c79aa1d2c79",
          "url": "https://github.com/anpawo/video-code/commit/644a4125a9b493362d95bec257dc982c225b6a5e"
        },
        "date": 1792070014426,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "5c52b441b71bc52f04c9071cf8194d28f544c502",
          "message": "timeline: zoom out to a quarter of the whole scene (#397)\n\nThe farthest zoom was the whole scene across the pane (100 %, 22 px/s for the\n60 s tutorial scene), edge to edge, which still read as a timeline going on\npast it. The slider now goes on down to a quarter of that: the whole scene in\na quarter of the pane, with the room around it. ⇧Z still goes to 100 %. A\nshort scene, which fits at 25 px/s, stops at a quarter of 25.\n\ntest/template_fold_test.py: the 200 s scene's floor is 1.67 px/s for a fit\nof 6.69; it was the fit itself before.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T15:18:03+02:00",
          "tree_id": "38b363db1b7eecc1d6f15a0a253e37985f6c851e",
          "url": "https://github.com/anpawo/video-code/commit/5c52b441b71bc52f04c9071cf8194d28f544c502"
        },
        "date": 1792070479095,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "b42a18bfbc2dd4a0855c7e38bdbd0f38d7f8c4a5",
          "message": "board: templates as blocks, nested calls inside, wait for his eye (93, #398)\n\nThe zoom out to a quarter of the scene (#397) has no row: its commit is the\nrecord, and FEATURES_TODO's C18 says it.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SPxsxAbAwXEMCiLh9rgYvS",
          "timestamp": "2026-10-15T15:19:04+02:00",
          "tree_id": "4e5055e04c8eae5968e4b54cae2b9d629cd5b3fa",
          "url": "https://github.com/anpawo/video-code/commit/b42a18bfbc2dd4a0855c7e38bdbd0f38d7f8c4a5"
        },
        "date": 1792071023395,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "435bbfe504ccc70be871125e92ca4e6b1bc6795f",
          "message": "ci: workflow and job names say what they run (#399)\n\nThe Actions tab listed CI, Mirror, Nightly and jobs called \"fast gates\"\nor \"remember\": none said what runs. GitHub has no description key for a\nworkflow, so each one writes a one-line description to its run page\nthrough $GITHUB_STEP_SUMMARY. main is not protected and has no ruleset,\nso no required check matched the old job names.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Bj7KxxnMrCX247AH2mDLBh",
          "timestamp": "2026-10-15T15:51:22+02:00",
          "tree_id": "5c8ad5bb3771c11654bd75972ab7f3634d7cd8e3",
          "url": "https://github.com/anpawo/video-code/commit/435bbfe504ccc70be871125e92ca4e6b1bc6795f"
        },
        "date": 1792072415772,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "95285ea16f29a06680bdfa4e8bb05fbf4fa663fd",
          "message": "test: every pushed line of videocode/ runs under a test, and its mutants die (#400)\n\ncoverage_check.py only asked whether a new public name appears in a test:\na new branch inside an old function, or a line no test runs, passed every\ngate. The Linux build lane now records which library lines each test file\nruns (stdlib sys.monitoring, through a sitecustomize, so the tests'\nsubprocesses and the interpreter inside ./video-code count too), refuses\nan added line that no test runs, and refuses a mutant of an added line\n(comparison, arithmetic, and/or, booleans, numbers) that every test\nrunning it lets through. A line that cannot be held to that says why with\n`# untested: <why>`.\n\nNot in the pre-commit hook: it needs the whole suite, minutes against\nthe hook's 15 s. Locally `python3 test/mutants.py` works in a throwaway\nworktree, never in the shared tree.\n\nMeasured on af63791 (#398): 22 lines of code, 2 run by no test, 13\nmutants killed, 2 survived, all in Context's frame walk, 3 min 44 s.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Bj7KxxnMrCX247AH2mDLBh",
          "timestamp": "2026-10-15T16:16:55+02:00",
          "tree_id": "8da4f25ea0685e8f8690d6c1b1a0522f1d346141",
          "url": "https://github.com/anpawo/video-code/commit/95285ea16f29a06680bdfa4e8bb05fbf4fa663fd"
        },
        "date": 1792073939949,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "91091565+Hip-po@users.noreply.github.com",
            "name": "hip-po",
            "username": "Hip-po"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b09ae881af96bb176ef2d106b4a5ca1b9c877755",
          "message": "Merge pull request #403 from anpawo/feature/401-contributing\n\nCONTRIBUTING.md, and the README generator keeps Contributing and License",
          "timestamp": "2026-10-15T16:38:22+02:00",
          "tree_id": "96ac0139e1b62e1b1f56b36cbafc066586f1de3c",
          "url": "https://github.com/anpawo/video-code/commit/b09ae881af96bb176ef2d106b4a5ca1b9c877755"
        },
        "date": 1792075203151,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "ed6d31faf74f8442e41ca6a499263d065ab95ee8",
          "message": "test: a template's clip name, for a class, a method and a module (#404)\n\ntest/mutants.py on af63791 (#398) found Context._templateCall half\ntested: no test ran the name of a template written as a class or as a\nmodule, and the two comparisons that tell those apart from a function\ncould be turned round with every test still green. One scene run through\nexecSource, with a function, a class, a method and a module beside it,\nnow holds each to the name it is given.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Bj7KxxnMrCX247AH2mDLBh",
          "timestamp": "2026-10-15T16:40:07+02:00",
          "tree_id": "bdff533d84a72e711e48dd0dd46dc2097ad840f1",
          "url": "https://github.com/anpawo/video-code/commit/ed6d31faf74f8442e41ca6a499263d065ab95ee8"
        },
        "date": 1792075767190,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "7cb64003df7599390af71003b5594019934a29da",
          "message": "ci: the weekly audit runs as a GitHub Action again, on the subscription (#405)\n\nThe claude.ai routine kept its schedule, its five prompt overrides and its\nruns outside the repository. claude-code-action with CLAUDE_CODE_OAUTH_TOKEN\nruns on the same subscription as the routine, so none of what made the\n18/09 workflow heavy comes back: no API key, no protected environment, no\nvalidator.\n\naudit.md now says what the routine's prompt used to override: English, no\nemail, draft pull requests only, earlier claude/audit-* pull requests as its\nmemory, assigned to anpawo. The perf half goes: its trial ended on 16/10 and,\nwith no email, its questions had nowhere to go. The workflow passes no\ngithub_token, so its pull requests come from the Claude GitHub App and CI\nruns on them.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-21T16:07:50+02:00",
          "tree_id": "0a0d839bfebd84262caf3df9f2116edae2d0b429",
          "url": "https://github.com/anpawo/video-code/commit/7cb64003df7599390af71003b5594019934a29da"
        },
        "date": 1792591789327,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "6719301ad3d637058c753a6c6a06631049dd0a8b",
          "message": "ci: the perf curve site is deployed by CI, not by GitHub's pages-build-deployment (#407)\n\nGitHub's own Pages build showed in the Actions list as\n`pages-build-deployment`, the one name there that does not say what runs,\nand no setting renames it. Pages now builds from Actions: a `pages` job,\nafter `history` has pushed the curve to gh-pages, deploys that branch on\npushes to main. The branch holds only dev/bench, so dropping the legacy\nbuild's Jekyll pass changes nothing on the site.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-21T16:26:44+02:00",
          "tree_id": "3af8f63dbba0fb89ad0a42dec6ce8dbdc63112fe",
          "url": "https://github.com/anpawo/video-code/commit/6719301ad3d637058c753a6c6a06631049dd0a8b"
        },
        "date": 1792592923314,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "807fb9b0080fd0d9c5cfd97bc3de7e7d3f172da9",
          "message": "ci: main only takes pull requests Claude has reviewed; .github only changes through Marius (#408)\n\nThe Claude token was a repository secret, and a repository secret reaches\nany workflow that anyone with write access writes, on any branch. The old\ntoken is revoked. The new one goes in the environment `claude`, which only\na job running on main can open, and main's workflows now only change with\nMarius's approval (.github/CODEOWNERS, enforced by the ruleset `main`).\n\nreview.yaml runs on pull_request_target, so the file that holds the token\nis always main's, and it never checks out the pull request's code: Claude\nreads the diff through gh and git, comments, and posts the check\n`Claude review` with the Claude GitHub App's token. The ruleset requires\nthat check from that app, so no workflow token can post it instead.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-22T12:43:09+02:00",
          "tree_id": "fe763bced673034f202b62d2eb9576dcae9cd1ef",
          "url": "https://github.com/anpawo/video-code/commit/807fb9b0080fd0d9c5cfd97bc3de7e7d3f172da9"
        },
        "date": 1792665900290,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "c2183d14edf7982d376ee32ae2c8ff02018da2dc",
          "message": "ci: Claude merges the pull requests its review passes, through the same gate (#408)\n\nMarius wants the review to merge what it judges worth it. After posting a\ngreen `Claude review` check, Claude merges with a merge commit, and leaves\nopen a pull request that touches .github/ or asks to wait.\n\nThe Claude GitHub App is off the ruleset's bypass list: with it, a pull\nrequest that talked Claude into merging could have landed a .github change\nwithout Marius. Nothing it does needed the bypass: the audit pushes to\nclaude/audit-* branches only.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-22T13:43:55+02:00",
          "tree_id": "5a9a0dbc8cd7c6ab0beb316dbdc113acc8e53bda",
          "url": "https://github.com/anpawo/video-code/commit/c2183d14edf7982d376ee32ae2c8ff02018da2dc"
        },
        "date": 1792669557983,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "29c8b60ef5c0708037f33ec2029e8347c4af023b",
          "message": "ci: Claude reviews and never merges; its commands run without the Claude token (#408)\n\nMarius reversed the merge step: people merge, once Claude's check is green\nand nothing under .github/ changed. The review's app token now asks for\ncontents: read, so it cannot merge or push whatever a pull request asks of\nClaude.\n\nBoth Claude jobs set CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: the commands Claude\nruns, the audit's tests included, get no Claude token in their environment\nand run apart from Claude's process. That is the path left to the token\nonce main is gated: code merged into main runs in the Monday audit, and a\npull request can try to talk the review into printing it.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-22T14:37:05+02:00",
          "tree_id": "8498691529787873a20859bc51fe4112e3fdaa0a",
          "url": "https://github.com/anpawo/video-code/commit/29c8b60ef5c0708037f33ec2029e8347c4af023b"
        },
        "date": 1792672720782,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "e4dd5986480aa9882fc10626cdd99496c1e7a10f",
          "message": "ci: the Claude jobs run again: the review starts from workflow_run, both install bubblewrap (#408)\n\nThe first review runs failed before Claude started: Anthropic's token\nexchange answers \"Invalid OIDC token\" to pull_request_target\n(anthropics/claude-code-action#713). review-request.yaml now runs on the\npull request with no token, and its completion starts review.yaml from\nmain, through workflow_run.\n\nAnd CLAUDE_CODE_SUBPROCESS_ENV_SCRUB, set in 29c8b60, makes Claude Code\nrefuse to start without bubblewrap: the audit dispatched today failed on\nit. Both jobs install it first, as the action does for\nallowed_non_write_users.\n\nMeasured: from a branch the exchange refuses a token to a new workflow, to\nmain's review.yaml path with other content and to a job with an\nenvironment (all \"Invalid OIDC token\"); from main, the audit with the\nclaude environment got its token.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-22T16:02:10+02:00",
          "tree_id": "8e6e2f5bc14b151db45c3fb0f46f95ba2259befc",
          "url": "https://github.com/anpawo/video-code/commit/e4dd5986480aa9882fc10626cdd99496c1e7a10f"
        },
        "date": 1792677827359,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "committer": {
            "email": "rousset.marius13@gmail.com",
            "name": "marius rousset",
            "username": "anpawo"
          },
          "distinct": true,
          "id": "50e4eeb2fc22282bd701336c38fc75a242c7cc15",
          "message": "ci: the mirror's key only opens from main, and is a key of its own (#413)\n\nGIT_SSH_PRIVATE_KEY was a repository secret, readable by any workflow pushed on\nany branch, and held the key of Marius's old Asus laptop, which opens every\nrepository he can push to. A new key, used for nothing else, now lives in the\nenvironment `mirror`, which only main can open: cd-mirror.yaml runs on every push\nwith no secret and starts mirror.yaml from main, which pushes. cd-mirror.yaml\nkeeps its name so a branch with its old version still starts the mirror.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0186gMvnTegkhL92eaHC5dNT",
          "timestamp": "2026-10-22T20:56:42+02:00",
          "tree_id": "f824ec80e4c6e09fccaef66986f3e3baeddfabb3",
          "url": "https://github.com/anpawo/video-code/commit/50e4eeb2fc22282bd701336c38fc75a242c7cc15"
        },
        "date": 1792699507298,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "91091565+Hip-po@users.noreply.github.com",
            "name": "hip-po",
            "username": "Hip-po"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "67732ccfe7c2aef807614e91abc2a46a065f6103",
          "message": "Merge pull request #439 from anpawo/docs/438-first-contribution\n\ndocs: CONTRIBUTING says where a first contribution starts (#438)",
          "timestamp": "2026-10-23T00:21:09+02:00",
          "tree_id": "b59aae90ce35577a0623ecdf052d4d7a8aa5f7ea",
          "url": "https://github.com/anpawo/video-code/commit/67732ccfe7c2aef807614e91abc2a46a065f6103"
        },
        "date": 1792710378981,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "bake/applyCalls",
            "value": 21767,
            "unit": "count"
          },
          {
            "name": "bake/entries",
            "value": 18980,
            "unit": "count"
          },
          {
            "name": "bake/inputs",
            "value": 564,
            "unit": "count"
          },
          {
            "name": "render/msPerFrame",
            "value": 6.5429,
            "unit": "ms"
          },
          {
            "name": "render/total",
            "value": 2.4732,
            "unit": "s"
          },
          {
            "name": "render/load",
            "value": 0.5103,
            "unit": "s"
          },
          {
            "name": "render/peakRss",
            "value": 461.2031,
            "unit": "MB"
          }
        ]
      }
    ]
  }
}