"use client";

import { useEffect, useRef } from "react";
import { createStrands, qualityForWidth, type Strand } from "@/lib/tesseract-geometry";

export function TesseractBackground() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const ctx = element.getContext("2d");
    if (!ctx) return;
    const context = ctx;
    const palette = window.getComputedStyle(element);
    const orbitRgb = palette.getPropertyValue("--rp-orbit-rgb").trim() || "213, 215, 232";
    const glowRgb = palette.getPropertyValue("--rp-glow-rgb").trim() || "171, 146, 255";
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0, height = 0, frame = 0, last = 0, elapsed = 0;
    let quality = qualityForWidth(window.innerWidth);
    let strands: Strand[] = createStrands(quality);
    function resize() {
      if (!element) return;
      const bounds = element.getBoundingClientRect();
      width = bounds.width; height = bounds.height;
      if (width <= 0 || height <= 0) return;
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio);
      context.setTransform(element.width / width, 0, 0, element.height / height, 0, 0);
      const next = qualityForWidth(width);
      if (next.strands !== quality.strands) { quality = next; strands = createStrands(quality); }
      if (!document.hidden) draw();
    }
    function draw() {
      context.clearRect(0, 0, width, height);
      const scale = Math.max(width, height) * 0.5;
      const rotation = elapsed * Math.PI * 2 / 110000;
      const cs = Math.cos(rotation), sn = Math.sin(rotation);
      const breath = 0.9 + 0.1 * Math.sin(elapsed * Math.PI * 2 / 11000);
      for (const strand of strands) {
        context.beginPath();
        context.setLineDash(strand.dotted ? [1, 7] : []);
        const pts = strand.points;
        for (let j = 0; j < pts.length; j += 3) {
          const x = pts[j] * cs - pts[j + 2] * sn;
          const z = pts[j] * sn + pts[j + 2] * cs;
          const perspective = 2.8 / (2.8 + z);
          const px = width * 0.52 + x * scale * perspective;
          const py = height * 0.48 + pts[j + 1] * scale * perspective;
          if (j === 0) context.moveTo(px, py); else context.lineTo(px, py);
        }
        context.lineWidth = 0.55;
        context.strokeStyle = `rgba(${orbitRgb},${strand.brightness * breath})`;
        context.shadowColor = `rgba(${glowRgb},0.22)`;
        context.shadowBlur = strand.family === 0 && !strand.dotted ? 4 : 0;
        context.stroke();
        context.shadowBlur = 0;
        if (strand.family === 0 && !strand.dotted) {
          const count = pts.length / 3 - 1;
          const index = Math.floor((elapsed / 90 + strand.phase * 19) % count) * 3;
          const x = pts[index] * cs - pts[index + 2] * sn;
          const z = pts[index] * sn + pts[index + 2] * cs;
          const p = 2.8 / (2.8 + z);
          context.fillStyle = `rgba(${orbitRgb},${quality.glow * breath})`;
          context.beginPath(); context.arc(width * 0.52 + x * scale * p, height * 0.48 + pts[index + 1] * scale * p, 1.2, 0, Math.PI * 2); context.fill();
        }
      }
      context.setLineDash([]);
    }
    function tick(now: number) {
      if (document.hidden || motion.matches) { frame = 0; return; }
      if (!last) last = now;
      const delta = now - last;
      if (delta >= 1000 / quality.fps) { elapsed += Math.min(delta, 100); last = now; draw(); }
      frame = requestAnimationFrame(tick);
    }
    function sync() {
      if (frame) cancelAnimationFrame(frame);
      frame = 0; last = 0;
      if (!document.hidden && !motion.matches) frame = requestAnimationFrame(tick);
      else if (!document.hidden) draw();
    }
    resize(); sync();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(element);
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", sync);
    motion.addEventListener("change", sync);
    return () => { if (frame) cancelAnimationFrame(frame); observer?.disconnect(); window.removeEventListener("resize", resize); document.removeEventListener("visibilitychange", sync); motion.removeEventListener("change", sync); };
  }, []);
  return <div className="orbital-background" aria-hidden="true"><canvas ref={canvas} /></div>;
}
