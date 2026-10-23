import React from "react";
import { Composition } from "remotion";
import rawCaptions from "./captions.json";
import { Caption, CaptionVideo } from "./CaptionVideo";

const captions = rawCaptions as Caption[];

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="CaptionVideo"
      component={CaptionVideo}
      durationInFrames={474}
      fps={30}
      width={360}
      height={640}
      defaultProps={{ captions }}
    />
    <Composition
      id="CaptionVideo1080"
      component={CaptionVideo}
      durationInFrames={474}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ captions }}
    />
    </>
  );
};
