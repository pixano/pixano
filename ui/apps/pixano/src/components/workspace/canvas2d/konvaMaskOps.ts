/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import simplify from "simplify-js";

import { m_part, l_part } from "$lib/utils/maskUtils";

// --- Parsed polygon cache for sceneFunc / smoothSceneFunc ---
type ParsedPolygon = { start: { x: number; y: number }; rest: { x: number; y: number }[] };
const parsedPolygonCache = new Map<string, ParsedPolygon>();

function getCachedParsedPolygon(svgPath: string): ParsedPolygon {
  let cached = parsedPolygonCache.get(svgPath);
  if (!cached) {
    const start = m_part(svgPath);
    const rest = l_part(svgPath);
    cached = { start, rest };
    parsedPolygonCache.set(svgPath, cached);
  }
  return cached;
}

/** Clear the parsed polygon cache (call on item switch). */
export function clearParsedCache(): void {
  parsedPolygonCache.clear();
}

// --- Simplified polygon cache for smoothSceneFunc ---
type SmoothedPolygon = {
  points: { x: number; y: number }[];
  segments: {
    cp1: { x: number; y: number };
    cp2: { x: number; y: number };
    end: { x: number; y: number };
    sharp: boolean;
  }[];
} | null;
const smoothedPolygonCache = new Map<string, SmoothedPolygon>();

export const sceneFunc = (ctx: Konva.Context, shape: Konva.Shape, svg: string[]) => {
  ctx.beginPath();
  for (let i = 0; i < svg.length; ++i) {
    const cached = getCachedParsedPolygon(svg[i]);
    ctx.moveTo(cached.start.x, cached.start.y);
    for (const pt of cached.rest) {
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.closePath();
  }
  // Use even-odd fill to support holes (inner polygons)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
  rawCtx.fillStyle = shape.fill() as string;
  rawCtx.fill("evenodd");
  ctx.strokeShape(shape);
};

// --- Smooth contour rendering ---

// Tuning constants for smooth rendering
const SMOOTH_EPSILON = 1.0; // RDP simplification tolerance in pixels (tighter = keep more shape-defining points)
const SMOOTH_TENSION = 0.7; // Catmull-Rom spline tension (higher = tighter curves, less overshoot)
const SHARP_CORNER_THRESHOLD = Math.PI * 0.4; // ~72° — angles below this use lineTo instead of bezierCurveTo

/**
 * Compute the angle at vertex p1 between edges p0→p1 and p1→p2.
 * Returns angle in radians [0, π].
 */
function angleBetween(
  p0: { x: number; y: number },
  p1: { x: number; y: number },
  p2: { x: number; y: number },
): number {
  const ax = p0.x - p1.x;
  const ay = p0.y - p1.y;
  const bx = p2.x - p1.x;
  const by = p2.y - p1.y;
  const dot = ax * bx + ay * by;
  const magA = Math.sqrt(ax * ax + ay * ay);
  const magB = Math.sqrt(bx * bx + by * by);
  if (magA === 0 || magB === 0) return Math.PI; // degenerate — treat as straight
  const cosAngle = Math.max(-1, Math.min(1, dot / (magA * magB)));
  return Math.acos(cosAngle);
}

/** Extract all {x, y} points from one SVG path string. */
function extractPoints(svgPath: string): { x: number; y: number }[] {
  const start = m_part(svgPath);
  const rest = l_part(svgPath);
  return [start, ...rest];
}

/**
 * Convert a closed polygon to cubic Bezier control points using Catmull-Rom splines.
 * For each segment P[i] → P[i+1]:
 *   cp1 = P[i]   + (P[i+1] - P[i-1]) / (6 * tension)
 *   cp2 = P[i+1] - (P[i+2] - P[i])   / (6 * tension)
 *
 * Sharp corners (angle < SHARP_CORNER_THRESHOLD) are flagged so the renderer
 * can use lineTo instead of bezierCurveTo, preventing overshoot artifacts.
 * Control point displacement is also clamped to half the segment length.
 */
function catmullRomToBezier(
  points: { x: number; y: number }[],
  tension: number = SMOOTH_TENSION,
): {
  cp1: { x: number; y: number };
  cp2: { x: number; y: number };
  end: { x: number; y: number };
  sharp: boolean;
}[] {
  const n = points.length;
  const segments: {
    cp1: { x: number; y: number };
    cp2: { x: number; y: number };
    end: { x: number; y: number };
    sharp: boolean;
  }[] = [];
  const t6 = 6 * tension;

  // Precompute angles at each vertex
  const angles: number[] = [];
  for (let i = 0; i < n; i++) {
    const prev = points[(i - 1 + n) % n];
    const curr = points[i];
    const next = points[(i + 1) % n];
    angles.push(angleBetween(prev, curr, next));
  }

  for (let i = 0; i < n; i++) {
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];

    const startSharp = angles[i] < SHARP_CORNER_THRESHOLD;
    const endSharp = angles[(i + 1) % n] < SHARP_CORNER_THRESHOLD;

    if (startSharp || endSharp) {
      // Either endpoint is a sharp corner — use straight line
      segments.push({
        cp1: { x: p1.x, y: p1.y },
        cp2: { x: p2.x, y: p2.y },
        end: { x: p2.x, y: p2.y },
        sharp: true,
      });
    } else {
      // Compute raw control points
      let cp1x = p1.x + (p2.x - p0.x) / t6;
      let cp1y = p1.y + (p2.y - p0.y) / t6;
      let cp2x = p2.x - (p3.x - p1.x) / t6;
      let cp2y = p2.y - (p3.y - p1.y) / t6;

      // Clamp control point displacement to half the segment length
      const segDx = p2.x - p1.x;
      const segDy = p2.y - p1.y;
      const maxDist = Math.sqrt(segDx * segDx + segDy * segDy) * 0.5;

      // Clamp cp1 displacement from p1
      const d1x = cp1x - p1.x;
      const d1y = cp1y - p1.y;
      const dist1 = Math.sqrt(d1x * d1x + d1y * d1y);
      if (dist1 > maxDist && dist1 > 0) {
        const scale = maxDist / dist1;
        cp1x = p1.x + d1x * scale;
        cp1y = p1.y + d1y * scale;
      }

      // Clamp cp2 displacement from p2
      const d2x = cp2x - p2.x;
      const d2y = cp2y - p2.y;
      const dist2 = Math.sqrt(d2x * d2x + d2y * d2y);
      if (dist2 > maxDist && dist2 > 0) {
        const scale = maxDist / dist2;
        cp2x = p2.x + d2x * scale;
        cp2y = p2.y + d2y * scale;
      }

      segments.push({
        cp1: { x: cp1x, y: cp1y },
        cp2: { x: cp2x, y: cp2y },
        end: { x: p2.x, y: p2.y },
        sharp: false,
      });
    }
  }

  return segments;
}

/**
 * Smooth scene rendering function: simplify polygon + Catmull-Rom cubic Bezier curves.
 * Use in display mode for beautiful contours; editing mode should keep original sceneFunc.
 */
export const smoothSceneFunc = (
  ctx: Konva.Context,
  shape: Konva.Shape,
  svg: string[],
  epsilon: number = SMOOTH_EPSILON,
  tension: number = SMOOTH_TENSION,
) => {
  ctx.beginPath();
  for (let i = 0; i < svg.length; i++) {
    // Use cache to avoid re-simplifying and re-computing bezier every frame
    const cacheKey = `${svg[i]}|${epsilon}|${tension}`;
    let cached = smoothedPolygonCache.get(cacheKey);
    if (!cached) {
      let points = extractPoints(svg[i]);
      points = simplify(points, epsilon, true);
      if (points.length < 4) {
        cached = { points, segments: [] };
      } else {
        cached = { points, segments: catmullRomToBezier(points, tension) };
      }
      smoothedPolygonCache.set(cacheKey, cached);
    }

    const { points, segments } = cached;
    if (segments.length === 0) {
      // Too few points for spline — fall back to straight lines
      ctx.moveTo(points[0].x, points[0].y);
      for (let j = 1; j < points.length; j++) {
        ctx.lineTo(points[j].x, points[j].y);
      }
      ctx.closePath();
    } else {
      ctx.moveTo(points[0].x, points[0].y);
      for (const seg of segments) {
        if (seg.sharp) {
          ctx.lineTo(seg.end.x, seg.end.y);
        } else {
          ctx.bezierCurveTo(seg.cp1.x, seg.cp1.y, seg.cp2.x, seg.cp2.y, seg.end.x, seg.end.y);
        }
      }
      ctx.closePath();
    }
  }
  // Use even-odd fill to support holes (inner polygons)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawCtx2 = (ctx as any)._context as CanvasRenderingContext2D;
  rawCtx2.fillStyle = shape.fill() as string;
  rawCtx2.fill("evenodd");
  ctx.strokeShape(shape);
};
