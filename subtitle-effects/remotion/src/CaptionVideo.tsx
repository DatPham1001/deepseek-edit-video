import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type Word = { start: number; end: number; text: string };
export type Caption = {
  start: number;
  end: number;
  words: Word[];
  accent: string[];
  style: "normal" | "danger" | "gold" | "hero";
  emoji?: string;
  popup?: boolean;
  lineBreak?: number;
  x?: number;
  y?: number;
};

const SANS = '"Segoe UI", Arial, sans-serif';

const palette = (style: Caption["style"]) => {
  if (style === "danger") {
    return { accent: "#FF4D4D", glow: "rgba(255,60,60,.75)" };
  }
  if (style === "gold" || style === "hero") {
    return { accent: "#FFD166", glow: "rgba(255,209,102,.8)" };
  }
  return { accent: "#FFB020", glow: "rgba(255,176,32,.7)" };
};

const CaptionLayer: React.FC<{ cap: Caption }> = ({ cap }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const k = width / 360;
  const t = frame / fps;
  const local = frame - cap.start * fps;
  const popup = Boolean(cap.popup);
  const enter = spring({
    frame: Math.max(0, local),
    fps,
    config: {
      damping: popup ? 8 : 13,
      stiffness: popup ? 280 : 220,
      mass: 0.55,
    },
  });
  const exit = interpolate(t, [cap.end - 0.09, cap.end], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const activeIndex = cap.words.findIndex(
    (w) => t >= w.start && t < w.end,
  );
  const pal = palette(cap.style);
  const isHero = cap.style === "hero";
  const shake =
    cap.style === "danger" && local < 9
      ? Math.sin(local * 2.4) * 2.5 * (1 - local / 9)
      : 0;
  const breakAt =
    cap.lineBreak && cap.lineBreak < cap.words.length
      ? cap.lineBreak
      : cap.words.length;
  const rows = [
    cap.words.slice(0, breakAt),
    cap.words.slice(breakAt),
  ].filter((r) => r.length);

  return (
    <div
      style={{
        position: "absolute",
        left: `${cap.x ?? 50}%`,
        top: `${cap.y ?? (popup ? 50 : 79.7)}%`,
        width: "max-content",
        maxWidth: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "0 9px",
        opacity: Math.min(enter, exit),
        transform: `translate(-50%, -50%) translateY(${
          popup ? 0 : (1 - enter) * 12
        }px) translateX(${shake}px)`,
      }}
    >
      {popup ? (
        <div
          style={{
            position: "absolute",
            width: 300 * k,
            height: 300 * k,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${pal.glow} 0%, transparent 68%)`,
            opacity: interpolate(local, [0, 4, 14], [0, 0.6, 0.12], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            transform: `scale(${0.4 + enter * 0.9})`,
          }}
        />
      ) : null}
      {cap.emoji === "🇻🇳" ? (
        <div
          style={{
            position: "absolute",
            top: -42 * k,
            right: 20 * k,
            width: 46 * k,
            height: 30 * k,
            borderRadius: 4 * k,
            background: "#DA251D",
            border: `${2 * k}px solid #fff`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 10px rgba(0,0,0,.6)",
            transform: `scale(${0.5 + enter * 0.5}) rotate(${
              (1 - enter) * -14
            }deg)`,
          }}
        >
          <div
            style={{
              color: "#FFD166",
              fontSize: 19 * k,
              lineHeight: 1,
              transform: "translateY(-1px)",
            }}
          >
            ★
          </div>
        </div>
      ) : cap.emoji ? (
        <div
          style={{
            position: "absolute",
            top: -34 * k,
            right: 22 * k,
            fontSize: (isHero ? 46 : 34) * k,
            transform: `scale(${0.5 + enter * 0.5}) rotate(${
              (1 - enter) * -18
            }deg)`,
            filter: "drop-shadow(0 4px 6px rgba(0,0,0,.65))",
          }}
        >
          {cap.emoji}
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 2 * k,
          maxWidth: (popup ? 344 : 310) * k,
          padding: popup
            ? `${12 * k}px ${12 * k}px ${14 * k}px`
            : `${3 * k}px ${7 * k}px ${4 * k}px`,
          borderRadius: (popup ? 18 : 10) * k,
          background: popup ? "rgba(0,0,0,.78)" : "rgba(0,0,0,.48)",
          border: popup
            ? `${2 * k}px solid ${pal.accent}`
            : `1px solid rgba(255,255,255,.10)`,
          boxShadow: "0 8px 22px rgba(0,0,0,.35)",
          transform: popup
            ? `scale(${0.55 + enter * 0.45})`
            : `scale(${0.94 + enter * 0.06})`,
        }}
      >
        {rows.map((row, ri) => (
          <div
            key={`row-${ri}`}
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "baseline",
              columnGap: (popup ? 18 : 6) * k,
              whiteSpace: "nowrap",
            }}
          >
            {row.map((w, j) => {
              const i = (ri === 0 ? 0 : breakAt) + j;
              const accent = cap.accent.includes(w.text);
              const active = i === activeIndex;
              const pop = active
                ? 1 + 0.13 * enter + 0.03 * Math.sin(local / 2)
                : 1;
              return (
                <span
                  key={`${w.text}-${i}`}
                  style={{
                    display: "inline-block",
                    fontFamily: SANS,
                    fontStyle: "normal",
                    fontWeight: 800,
                    fontSize:
                      (isHero
                        ? 34
                        : popup
                          ? cap.words.length >= 5
                            ? 24
                            : 27
                          : 17) * k,
                    lineHeight: 1.05,
                    textTransform: "uppercase",
                    color: accent ? pal.accent : active ? "#FFE066" : "#FFFFFF",
                    transform: `scale(${pop})`,
                    transformOrigin: "50% 80%",
                    WebkitTextStroke: popup
                      ? `${1 * k}px #000`
                      : `${0.5 * k}px #000`,
                    textShadow: popup
                      ? `0 3px 0 #000, 0 0 18px ${pal.glow}`
                      : "0 2px 4px rgba(0,0,0,.85)",
                    letterSpacing: 0.1 * k,
                    paddingBottom: isHero ? 2 * k : 0,
                  }}
                >
                  {w.text}
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

export const CaptionVideo: React.FC<{ captions: Caption[] }> = ({
  captions,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const current = captions.find((c) => t >= c.start && t < c.end);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo
        src={staticFile("clip.mp4")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      {current ? <CaptionLayer cap={current} /> : null}
    </AbsoluteFill>
  );
};
