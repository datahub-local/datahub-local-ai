/* HFConnectors: draw declared arrows from live element boxes.
 *
 * A hand-placed arrow is geometry the composer has to keep in sync with two boxes by hand,
 * and 17510 shipped arrows ending in empty space. This helper measures both endpoints at draw
 * time and places the head on the target's own edge, so that defect is unrepresentable.
 *
 * The geometry below is duplicated in session-lib.mjs `connectorGeometry` (same gap, head
 * length and width, same facing-edge choice): a browser script cannot import, and the Node
 * test checks one implementation while the DOM dump checks the other. Keep them identical.
 *
 * A classic script, not a module: the composition loads it as a sibling of gsap.min.js.
 * It does not auto-run; the composer calls HFConnectors.draw(...) after both endpoints exist.
 */
(function () {
  "use strict";

  var GAP = 8;
  var HEAD_LENGTH = 14;
  var HEAD_WIDTH = 10;

  function round2(n) {
    return Math.round(n * 100) / 100;
  }

  function boxOf(rect) {
    if (!rect || typeof rect !== "object") return null;
    var box = { x: Number(rect.x), y: Number(rect.y), w: Number(rect.w), h: Number(rect.h) };
    if (
      !isFinite(box.x) || !isFinite(box.y) || !isFinite(box.w) || !isFinite(box.h) ||
      box.w <= 0 || box.h <= 0
    ) {
      return null;
    }
    return box;
  }

  function geometry(rects, opts) {
    var options = opts || {};
    var head = options.head !== false;
    var a = boxOf(rects && rects.from);
    var b = boxOf(rects && rects.to);
    if (!a) return { ok: false, reason: "the box is missing" };
    if (!b) return { ok: false, reason: "the box is missing" };
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
      return { ok: false, reason: "the two boxes overlap" };
    }

    var acx = a.x + a.w / 2;
    var acy = a.y + a.h / 2;
    var bcx = b.x + b.w / 2;
    var bcy = b.y + b.h / 2;
    var dx = bcx - acx;
    var dy = bcy - acy;
    var x1;
    var y1;
    var x2;
    var y2;
    var dirX = 0;
    var dirY = 0;
    if (Math.abs(dx) >= Math.abs(dy)) {
      dirX = dx >= 0 ? 1 : -1;
      x1 = dirX > 0 ? a.x + a.w + GAP : a.x - GAP;
      x2 = dirX > 0 ? b.x - GAP : b.x + b.w + GAP;
      y1 = acy;
      y2 = bcy;
    } else {
      dirY = dy >= 0 ? 1 : -1;
      y1 = dirY > 0 ? a.y + a.h + GAP : a.y - GAP;
      y2 = dirY > 0 ? b.y - GAP : b.y + b.h + GAP;
      x1 = acx;
      x2 = bcx;
    }

    var span = dirX ? dirX * (x2 - x1) : dirY * (y2 - y1);
    var back = head ? Math.min(HEAD_LENGTH, Math.max(0, span)) : 0;
    var tipX = round2(x2);
    var tipY = round2(y2);
    var lineX = round2(x2 - dirX * back);
    var lineY = round2(y2 - dirY * back);
    var halfWidth = HEAD_WIDTH / 2;
    var headPoints = head
      ? [
          [tipX, tipY],
          [round2(lineX - dirY * halfWidth), round2(lineY - dirX * halfWidth)],
          [round2(lineX + dirY * halfWidth), round2(lineY + dirX * halfWidth)],
        ]
          .map(function (p) {
            return p[0] + "," + p[1];
          })
          .join(" ")
      : null;
    return {
      x1: round2(x1),
      y1: round2(y1),
      x2: lineX,
      y2: lineY,
      head: headPoints === null ? null : { points: headPoints },
      ok: true,
    };
  }

  function elementById(doc, id) {
    var name = String(id == null ? "" : id).replace(/^#/, "");
    return name ? doc.getElementById(name) : null;
  }

  function rectIn(element, origin) {
    var r = element.getBoundingClientRect();
    return { x: r.left - origin.left, y: r.top - origin.top, w: r.width, h: r.height };
  }

  function overlayFor(doc, compRect) {
    var scrollX = globalThis.scrollX || 0;
    var scrollY = globalThis.scrollY || 0;
    var width = Math.max(1, Math.round(compRect.width));
    var height = Math.max(1, Math.round(compRect.height));
    // Above the composition, below whatever the composer marks as its own top overlay.
    var z = "1";
    var above = doc.querySelector("[data-connector-above]");
    if (above && typeof globalThis.getComputedStyle === "function") {
      var aboveZ = parseInt(globalThis.getComputedStyle(above).zIndex, 10);
      if (isFinite(aboveZ) && aboveZ > 0) z = String(aboveZ - 1);
    }
    var svg = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    // Absolute with explicit offsets rather than inset:0: the composition is not necessarily
    // the containing block, and a wrong origin would put every line somewhere else.
    svg.setAttribute(
      "style",
      "position:absolute;left:" +
        Math.round(compRect.left + scrollX) +
        "px;top:" +
        Math.round(compRect.top + scrollY) +
        "px;width:" +
        width +
        "px;height:" +
        height +
        "px;pointer-events:none;z-index:" +
        z +
        ";overflow:visible"
    );
    svg.setAttribute("data-connectors", "");
    doc.body.appendChild(svg);
    return svg;
  }

  function draw(list, opts) {
    var options = opts || {};
    var doc = globalThis.document;
    var declarations = Array.isArray(list) ? list : [];
    var errors = [];
    var drawn = 0;
    var result = { ok: false, drawn: 0, errors: errors };
    if (!doc || !doc.body) return result;

    var composition = doc.querySelector("[data-composition-id]") || doc.body;
    var compRect = composition.getBoundingClientRect();
    // The overlay is appended to <body>, outside the composition, so `currentColor` there is the
    // page's default -- black on a dark composition, i.e. arrows that are present but unreadable.
    // The composition's own text colour is the brand's; `options.stroke` still overrides it.
    var ink = "currentColor";
    if (typeof globalThis.getComputedStyle === "function") {
      try {
        ink = globalThis.getComputedStyle(composition).color || ink;
      } catch (err) {
        // no computed style: currentColor as before
      }
    }
    var svg = overlayFor(doc, compRect);
    var reveal = typeof options.reveal === "number" && options.reveal > 0 ? options.reveal : 0;
    var elements = [];

    for (var i = 0; i < declarations.length; i += 1) {
      var decl = declarations[i] || {};
      var id = decl.id == null ? "" : String(decl.id);
      try {
        var fromEl = elementById(doc, decl.from);
        var toEl = elementById(doc, decl.to);
        if (!fromEl || !toEl) {
          var missing = [];
          if (!fromEl) missing.push(decl.from);
          if (!toEl) missing.push(decl.to);
          errors.push({ id: id, reason: "the element was not found: " + missing.join(", ") });
          continue;
        }
        var g = geometry(
          { from: rectIn(fromEl, compRect), to: rectIn(toEl, compRect) },
          { head: decl.head !== false }
        );
        if (!g.ok) {
          errors.push({ id: id, reason: g.reason });
          continue;
        }
        var line = doc.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(g.x1));
        line.setAttribute("y1", String(g.y1));
        line.setAttribute("x2", String(g.x2));
        line.setAttribute("y2", String(g.y2));
        line.setAttribute("stroke", options.stroke || ink);
        line.setAttribute("stroke-width", String(options.width || 2));
        line.setAttribute("stroke-linecap", "round");
        line.setAttribute("data-connector", id);
        elements.push(line);
        svg.appendChild(line);
        if (g.head) {
          var head = doc.createElementNS("http://www.w3.org/2000/svg", "polygon");
          head.setAttribute("points", g.head.points);
          head.setAttribute("fill", options.stroke || ink);
          head.setAttribute("data-connector-head", id);
          elements.push(head);
          svg.appendChild(head);
        }
        drawn += 1;
      } catch (err) {
        // A bad declaration is a recorded miss, never an exception out of draw.
        errors.push({ id: id, reason: String((err && err.message) || err) });
      }
    }

    if (reveal) {
      for (var j = 0; j < elements.length; j += 1) {
        elements[j].style.opacity = "0";
        elements[j].style.transition = "opacity " + reveal + "s linear";
      }
      // Flush the zero state, then fade in: the transition runs without a frame callback.
      svg.getBoundingClientRect();
      for (var k = 0; k < elements.length; k += 1) elements[k].style.opacity = "1";
    }

    result.ok = errors.length === 0;
    result.drawn = drawn;
    if (doc.documentElement && doc.documentElement.dataset) {
      doc.documentElement.dataset.hfConnectors = errors.length
        ? "error:" + errors.map(function (e) { return e.id; }).join(",")
        : "ok";
    }
    globalThis.__hfConnectors = { ok: result.ok, drawn: drawn, errors: errors };
    return result;
  }

  globalThis.HFConnectors = { draw: draw, _geometry: geometry };
})();
