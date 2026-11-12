"use client";

import React, { useState } from "react";

const DEFAULT_AVATAR_URL = "/avatars/default-avatar.svg";

interface UserAvatarProps {
  src?: string | null;
  alt: string;
  className?: string;
}

export function UserAvatar({ src, alt, className = "" }: UserAvatarProps) {
  const requestedSrc = src?.trim() || DEFAULT_AVATAR_URL;
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const imageSrc = failedSrc === requestedSrc ? DEFAULT_AVATAR_URL : requestedSrc;
  return (
    <div
      className={`shrink-0 overflow-hidden rounded-full bg-white ${className}`}
    >
      <img
        src={imageSrc}
        alt={alt}
        className="h-full w-full object-cover"
        onError={() => {
          if (imageSrc !== DEFAULT_AVATAR_URL) setFailedSrc(requestedSrc);
        }}
      />
    </div>
  );
}
