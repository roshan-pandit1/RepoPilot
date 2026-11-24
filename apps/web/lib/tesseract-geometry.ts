export interface Strand { points: Float32Array; family: number; phase: number; dotted: boolean; brightness: number }
export interface OrbitalQuality { strands: number; samples: number; fps: number; glow: number }

export function qualityForWidth(width: number): OrbitalQuality {
  return width < 640 ? { strands: 48, samples: 64, fps: 30, glow: 0.14 } : { strands: 100, samples: 96, fps: 30, glow: 0.18 };
}

// Deterministic nested ellipses, grouped into five oriented orbital families.
export function createStrands(quality: OrbitalQuality): Strand[] {
  return Array.from({ length: quality.strands }, (_, i) => {
    const family = i % 5;
    const layer = Math.floor(i / 5);
    const layers = Math.ceil(quality.strands / 5);
    const t = layer / layers;
    const points = new Float32Array((quality.samples + 1) * 3);
    const a = 0.48 + t * 1.14;
    const b = 0.23 + t * 0.54;
    const tilt = [0.12, 1.06, -1.05, 1.57, -0.48][family];
    const ct = Math.cos(tilt), st = Math.sin(tilt);
    const phase = layer * 0.23 + family * 0.72;
    for (let j = 0; j <= quality.samples; j++) {
      const angle = j / quality.samples * Math.PI * 2;
      const x = a * Math.cos(angle);
      const y = b * Math.sin(angle);
      points[j * 3] = x * ct - y * st;
      points[j * 3 + 1] = x * st + y * ct;
      points[j * 3 + 2] = Math.sin(angle + phase) * (0.22 + t * 0.35);
    }
    return { points, family, phase, dotted: i % 7 === 0, brightness: 0.13 + (1 - t) * 0.18 };
  });
}
