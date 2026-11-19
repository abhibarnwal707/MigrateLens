/* MigrateLens site. Everything shown comes from window.ML_DATA (built by site/build_data.py). */
(function () {
  "use strict";
  var D = window.ML_DATA;
  var root = document.documentElement;
  root.classList.add("js-on");
  var NS = "http://www.w3.org/2000/svg";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var FIELDS = ["#d71e1e", "#1e4bd7", "#0c7866", "#ffe927"];
  var LABEL = {
    "iot-sns-sqs-ddb": "IoT fan-out", "java-synthetic-orders": "Java orders",
    "priority-mailer-ses": "SES mailer", "sam-messaging": "Messaging",
    "sns-email-china": "SNS mailer", "sqs-max-concurrency": "SQS limits", "twilio-apigw": "Twilio MMS"
  };

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    if (name === "text" && !("fill" in attrs)) n.setAttribute("fill", "#ffffff");
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function short(s) { return s.length > 11 ? s.replace("Secrets Manager", "Secrets").replace("SSM Parameter Store", "SSM").replace("API Gateway", "API GW").replace("Step Functions", "Step Fn") : s; }
  function shortG(s) { return s.replace("Cloud Run functions", "Run functions").replace("Secret Manager", "Secret Mgr").replace("Cloud Monitoring", "Monitoring").replace("Cloud Logging", "Logging").replace("Service Accounts", "Svc accounts"); }

  /* ---------- the board ---------- */
  function drawBoard(svg, app, onPin) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 400, pad = 18, refused = app.verdict !== "verified";
    var pins = app.services.map(function (s) { return { name: s.aws, s: s, bad: false }; });
    app.rejected_names.forEach(function (n) { pins.push({ name: n, s: null, bad: true }); });
    var perRow = pins.length > 6 ? Math.ceil(pins.length / 2) : pins.length;
    var gap = 8, pw = (W - 2 * pad - gap * (perRow - 1)) / perRow, ph = 40;
    var chip = { x: 70, y: 214, w: 260, h: 84 };

    // google pins: first listed product for each mapped service, de-duplicated
    var gNames = [];
    app.services.forEach(function (s) { var g = s.gcp[0] || "No equivalent"; if (gNames.indexOf(g) < 0) gNames.push(g); });
    var gPer = gNames.length > 4 ? Math.ceil(gNames.length / 2) : gNames.length;
    var gw = (W - 2 * pad - gap * (gPer - 1)) / gPer;

    var gTraces = el("g", {}, svg), gCur = el("g", {}, svg), gPins = el("g", {}, svg);

    // chip
    var c = el("g", {}, svg);
    el("rect", { x: chip.x, y: chip.y, width: chip.w, height: chip.h, fill: "#111111" }, c);
    for (var i = 0; i < 9; i++) {
      el("rect", { x: chip.x + 14 + i * 28, y: chip.y - 8, width: 10, height: 8, fill: "#6b6b6b" }, c);
      el("rect", { x: chip.x + 14 + i * 28, y: chip.y + chip.h, width: 10, height: 8, fill: "#6b6b6b" }, c);
    }
    var t1 = el("text", { x: W / 2, y: chip.y + 36, "text-anchor": "middle", "font-size": 19, "font-weight": 500 }, c);
    t1.textContent = "Guardrail";
    var t2 = el("text", { x: W / 2, y: chip.y + 62, "text-anchor": "middle", "font-size": 15, fill: refused ? "#ff6b6b" : "#4fd1b5" }, c);
    t2.textContent = refused ? "Could not verify" : "Verified · " + app.items_checked + " checks";
    el("rect", { class: "chip-glow", x: chip.x + chip.w - 22, y: chip.y + 10, width: 10, height: 10, fill: refused ? "#d71e1e" : "#4fd1b5" }, c);

    // AWS pins and their traces
    pins.forEach(function (p, idx) {
      var row = Math.floor(idx / perRow), col = idx % perRow;
      var x = pad + col * (pw + gap), y = 24 + row * (ph + 14);
      var cx = x + pw / 2, by = y + ph;
      var lane = chip.x + 20 + (idx + 0.5) * ((chip.w - 40) / pins.length);
      var y1 = chip.y - 22 - (idx % 4) * 9;
      var colr = p.bad ? "#d71e1e" : FIELDS[idx % 3 === 2 ? 2 : idx % 2];
      var d = "M" + cx + " " + by + " V" + y1 + " H" + lane + " V" + (chip.y - 8);
      var tr = el("path", { d: d, class: "trace draw", stroke: colr, pathLength: 1 }, gTraces);
      tr.style.animationDelay = (idx * 70) + "ms";
      if (p.bad) {
        // blown fuse where the unverifiable name meets the gate
        var fx = lane, fy = chip.y - 30;
        el("path", { d: "M" + (fx - 9) + " " + (fy - 9) + " L" + (fx + 9) + " " + (fy + 9) + " M" + (fx + 9) + " " + (fy - 9) + " L" + (fx - 9) + " " + (fy + 9), stroke: "#ffe927", "stroke-width": 5, fill: "none" }, gTraces);
      } else if (!refused) {
        el("path", { d: d, class: "current" }, gCur).style.animationDelay = (-idx * 0.2) + "s";
      }
      // continue from chip to the google pin (only when verified)
      if (!refused && p.s) {
        var g = p.s.gcp[0] || "No equivalent", gi = gNames.indexOf(g);
        var grow = Math.floor(gi / gPer), gcol = gi % gPer;
        var gx = pad + gcol * (gw + gap) + gw / 2, gy = 404 + grow * (ph + 14);
        var y2 = chip.y + chip.h + 22 + (idx % 4) * 9;
        var d2 = "M" + lane + " " + (chip.y + chip.h + 8) + " V" + y2 + " H" + gx + " V" + gy;
        var t = el("path", { d: d2, class: "trace draw", stroke: colr, pathLength: 1 }, gTraces);
        t.style.animationDelay = (400 + idx * 70) + "ms";
        if (g !== "No equivalent") el("path", { d: d2, class: "current" }, gCur).style.animationDelay = (-idx * 0.2 - 0.8) + "s";
      }
      var pg = el("g", { class: "pin", tabindex: 0, role: "button", "aria-label": p.name + (p.bad ? ", rejected" : "") }, gPins);
      el("rect", { x: x, y: y, width: pw, height: ph, fill: p.bad ? "#d71e1e" : "#ffffff" }, pg);
      var tx = el("text", { x: cx, y: y + 25, "text-anchor": "middle", "font-size": pw < 40 ? 11 : 13, "font-weight": 500, fill: p.bad ? "#ffffff" : "#111111" }, pg);
      tx.textContent = short(p.name);
      function show() { onPin && onPin(p, app); }
      pg.addEventListener("mouseenter", show); pg.addEventListener("focus", show); pg.addEventListener("click", show);
    });

    // google pins, or the refusal
    if (!refused) {
      gNames.forEach(function (g, gi) {
        var grow = Math.floor(gi / gPer), gcol = gi % gPer;
        var x = pad + gcol * (gw + gap), y = 404 + grow * (ph + 14), none = g === "No equivalent";
        el("rect", { x: x, y: y, width: gw, height: ph, fill: none ? "#242424" : "#0c7866" }, gPins);
        var t = el("text", { x: x + gw / 2, y: y + 25, "text-anchor": "middle", "font-size": gw < 70 ? 11 : 13, "font-weight": 500, fill: none ? "#b4b4b4" : "#ffffff" }, gPins);
        t.textContent = shortG(g);
      });
    } else {
      var r1 = el("text", { x: W / 2, y: 420, "text-anchor": "middle", "font-size": 17, "font-weight": 500 }, gPins);
      r1.textContent = "No plan. No artifacts.";
      var r2 = el("text", { x: W / 2, y: 446, "text-anchor": "middle", "font-size": 14, fill: "#b4b4b4" }, gPins);
      r2.textContent = app.drafts_rejected + " drafts rejected: " + app.rejected_names.join(", ") + " has no evidence";
    }
    var foot = el("text", { x: pad, y: 508, "font-size": 13, fill: "#b4b4b4" }, svg);
    foot.textContent = app.name + " · " + app.files + " files · " + app.llm_calls + " model calls";
  }

  function readoutFor(p, app) {
    if (p.bad) return p.name + " was named by the agent, but the detector found no evidence for it, so the guardrail rejected the plan.";
    var s = p.s;
    var g = s.gcp.length ? s.gcp.join(" or ") : "no Google Cloud equivalent";
    return s.aws + " → " + g + ". Evidence: " + s.evidence.join(", ") + (s.evidence_count > 3 ? " and " + (s.evidence_count - 3) + " more" : "") + ".";
  }

  /* ---------- numbers ---------- */
  document.querySelectorAll("[data-r]").forEach(function (n) {
    var v = D.results[n.getAttribute("data-r")];
    n.textContent = typeof v === "number" ? String(v) : v;
  });

  /* ---------- seven apps ---------- */
  var names = document.getElementById("names"), main = document.getElementById("main-board"), out = document.getElementById("readout");
  var current = 0;
  function select(i) {
    current = i;
    var app = D.apps[i];
    drawBoard(main, app, function (p, a) { out.textContent = readoutFor(p, a); });
    out.textContent = app.verdict === "verified"
      ? app.services.length + " services wired with evidence, plan verified on draft " + (app.retries + 1) + ", Terraform " + (app.terraform_ok ? "validates" : "not validated") + "."
      : "Refused: the agent named " + app.rejected_names.join(", ") + ", which the repo uses but the detector cannot prove.";
    names.querySelectorAll("button").forEach(function (b, j) { b.setAttribute("aria-pressed", String(j === i)); });
  }
  D.apps.forEach(function (app, i) {
    var li = document.createElement("li");
    var b = document.createElement("button");
    b.type = "button";
    if (app.verdict !== "verified") b.className = "refused";
    b.innerHTML = '<span class="nm"></span><span class="meta"></span>';
    b.querySelector(".nm").textContent = LABEL[app.name] || app.name;
    b.querySelector(".meta").textContent = app.style + (app.synthetic ? ", synthetic" : "") + " · " + (app.verdict === "verified" ? "verified" : "refused");
    b.addEventListener("mouseenter", function () { if (window.matchMedia("(hover: hover)").matches) select(i); });
    b.addEventListener("focus", function () { select(i); });
    b.addEventListener("click", function () { select(i); });
    li.appendChild(b); names.appendChild(li);
  });
  select(D.apps.findIndex(function (a) { return a.name === "twilio-apigw"; }));

  /* ---------- hero board: cycles through the verified apps ---------- */
  var hero = document.getElementById("hero-board");
  var verified = D.apps.filter(function (a) { return a.verdict === "verified"; });
  var h = 0;
  drawBoard(hero, verified[h]);
  if (!reduce) setInterval(function () { h = (h + 1) % verified.length; drawBoard(hero, verified[h]); }, 5200);

  /* ---------- the gate: one card, four states (the refused run) ---------- */
  var g = D.apps.find(function (a) { return a.verdict !== "verified"; }) || D.apps[0];
  function card(id, html) { document.getElementById(id).innerHTML = html; }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }
  card("card1", '<div class="ct">' + esc(g.name) + '</div><div class="row">Files read<b>' + g.files + '</b></div><div class="row">Executed<b>none</b></div><div class="row">Style<b>' + esc(g.style) + '</b></div><span class="tag wait">Reading</span>');
  card("card2", '<div class="ct">' + esc(g.name) + '</div>' + g.services.slice(0, 4).map(function (s) { return '<div class="row">' + esc(s.aws) + '<b>' + esc(s.evidence[0]) + '</b></div>'; }).join("") + '<div class="row">Services cited<b>' + g.services.length + '</b></div>');
  card("card3", '<div class="ct">' + esc(g.name) + '</div><div class="row">Names checked<b>' + g.items_checked + '</b></div><div class="row">Rejected<b>' + g.first_draft_violations + '</b></div><div class="bar"><i style="width:' + Math.round(100 * (g.items_checked - g.first_draft_violations) / g.items_checked) + '%"></i></div><div class="row">' + esc(g.rejected_names.join(", ")) + '<b>no evidence</b></div>');
  card("card4", '<div class="ct">' + esc(g.name) + '</div><div class="row">Drafts rejected<b>' + g.drafts_rejected + ' of 3</b></div><div class="row">Artifacts written<b>0</b></div><span class="tag no">Could not verify</span>');

  /* ---------- the wiring table ---------- */
  var table = document.getElementById("table");
  var usage = {};
  D.apps.forEach(function (a) { a.services.forEach(function (s) { usage[s.aws] = (usage[s.aws] || 0) + 1; }); });
  var groups = [
    ["Direct equivalents", D.mapping.filter(function (m) { return m.direct; })],
    ["No one-to-one match", D.mapping.filter(function (m) { return !m.direct && m.gcp.length; })],
    ["No Google Cloud equivalent", D.mapping.filter(function (m) { return !m.gcp.length; })]
  ];
  groups.forEach(function (grp) {
    var hd = document.createElement("div"); hd.className = "grp"; hd.textContent = grp[0]; table.appendChild(hd);
    grp[1].forEach(function (m) {
      var r = document.createElement("div"); r.className = "tr"; r.setAttribute("role", "row");
      var n = usage[m.aws] || 0;
      r.innerHTML = "<span></span><span></span><span class=soft></span><span></span>";
      r.children[0].textContent = m.aws;
      r.children[1].textContent = m.gcp.length ? m.gcp[0] : "Third-party provider";
      r.children[2].textContent = m.gcp.length > 1 ? "or " + m.gcp.slice(1).join(", ") : (m.direct ? "drop-in" : "redesign");
      r.children[3].textContent = n ? "in " + n + " app" + (n > 1 ? "s" : "") : "—";
      table.appendChild(r);
    });
  });

  /* ---------- entrances, staggered per section ---------- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var sibs = e.target.parentElement.querySelectorAll(".reveal");
      var idx = Array.prototype.indexOf.call(sibs, e.target);
      e.target.style.transitionDelay = (Math.max(idx, 0) * 80) + "ms";
      e.target.classList.add("in");
      io.unobserve(e.target);
    });
  }, { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach(function (n) { io.observe(n); });

  /* ---------- one moving picture: the 1947 newsreel, hand-patching segment, loaded only near view ---------- */
  var reel = document.getElementById("reel"), START = 34, END = 50;
  if (reel) {
    var vio = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) {
          if (!reel.getAttribute("src")) {
            reel.src = "media/arnhem-1947.webm#t=" + START;
            var seek = function () { if (reel.currentTime < START - 1) reel.currentTime = START; };
            reel.addEventListener("loadedmetadata", seek); reel.addEventListener("loadeddata", seek);
            reel.addEventListener("timeupdate", function () { if (reel.currentTime >= START - 0.5 && reel.currentTime < END) reel.classList.add("playing"); });
            reel.addEventListener("timeupdate", function () { if (reel.currentTime >= END || reel.currentTime < START - 1) reel.currentTime = START; });
          }
          if (!reduce) { var p = reel.play(); if (p && p.catch) p.catch(function () {}); }
        } else { reel.pause(); }
      });
    }, { rootMargin: "200px" });
    vio.observe(reel);
    if (!reduce) {
      window.addEventListener("scroll", function () {
        var r = reel.getBoundingClientRect(), vh = window.innerHeight;
        var p = Math.min(Math.max((vh - r.top) / (vh + r.height), 0), 1);
        reel.style.transform = "scale(" + (1.12 - p * 0.12) + ")";
      }, { passive: true });
    }
  }

  requestAnimationFrame(function () { root.classList.add("loaded"); });
})();
