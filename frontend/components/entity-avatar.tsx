"use client";

import { useState } from "react";
import {
  entityInitials,
  visualForEntity,
  type VisualAsset,
} from "@/lib/visual-assets";

export function EntityAvatar({
  kind,
  id,
  name,
  size = "md",
  className = "",
}: {
  kind: "investor" | "company";
  id: string;
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const asset = visualForEntity(kind, id);
  const dimensions = size === "sm" ? 32 : size === "lg" ? 64 : 44;
  const style = { width: dimensions, height: dimensions };

  return (
    <span
      className={`entity-avatar entity-avatar-${kind} ${className}`}
      style={style}
      title={asset ? `${asset.creator} · ${asset.license}` : undefined}
      data-testid={`entity-avatar-${kind}-${id.toLowerCase()}`}
    >
      <span aria-hidden>{entityInitials(name)}</span>
      {asset && !failed && (
        // Remote images are optional enhancement; the visible monogram remains
        // underneath if a host, redirect, or content policy blocks the asset.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={asset.src}
          alt={asset.alt}
          width={dimensions}
          height={dimensions}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}

export function AssetAttribution({ asset }: { asset: VisualAsset }) {
  return (
    <a href={asset.source} rel="noreferrer" target="_blank">
      {asset.alt}: {asset.creator}, {asset.license}
    </a>
  );
}
