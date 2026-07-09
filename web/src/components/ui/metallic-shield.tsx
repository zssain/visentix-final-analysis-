import React, { useState, useRef, useEffect } from "react";

interface MetallicShieldProps {
  focusField?: "email" | "password" | null;
}

export function MetallicShield({ focusField }: MetallicShieldProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rotateX, setRotateX] = useState(0);
  const [rotateY, setRotateY] = useState(0);
  const [shineX, setShineX] = useState(50);
  const [shineY, setShineY] = useState(50);
  const [isHovered, setIsHovered] = useState(false);

  // Sync state with active form field focus when not hovered
  useEffect(() => {
    if (isHovered) return;

    if (focusField === "email") {
      setRotateX(0);
      setRotateY(25);  // Tilt to face the left side (towards the form)
      setShineX(20);   // Specular reflection on the left
      setShineY(50);
    } else if (focusField === "password") {
      setRotateX(0);
      setRotateY(0);   // Facing the user
      setShineX(50);   // Centered shine
      setShineY(50);
    } else {
      setRotateX(0);
      setRotateY(0);
      setShineX(50);
      setShineY(50);
    }
  }, [focusField, isHovered]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    
    // Coordinates relative to center of the element
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Calculate rotation: max 18 degrees tilt (negative for left-to-right tracking)
    const rY = -((mouseX - width / 2) / (width / 2)) * 18;
    const rX = -((mouseY - height / 2) / (height / 2)) * 18;

    // Calculate specular reflection shine center (0 to 100 percent)
    const sX = (mouseX / width) * 100;
    const sY = (mouseY / height) * 100;

    setRotateX(rX);
    setRotateY(rY);
    setShineX(sX);
    setShineY(sY);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    // When leaving hover, let the useEffect restore the appropriate focusField alignment
    if (focusField === "email") {
      setRotateX(0);
      setRotateY(25);
      setShineX(20);
      setShineY(50);
    } else if (focusField === "password") {
      setRotateX(0);
      setRotateY(0);   // Facing the user
      setShineX(50);
      setShineY(50);
    } else {
      setRotateX(0);
      setRotateY(0);
      setShineX(50);
      setShineY(50);
    }
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        perspective: "1000px",
        display: "inline-block",
        cursor: "default",
        margin: "0 0 24px 0",
      }}
      aria-hidden="true"
    >
      <div
        style={{
          transform: `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${isHovered ? 1.08 : 1})`,
          transition: isHovered ? "transform 0.05s ease-out" : "transform 0.6s cubic-bezier(0.25, 1, 0.5, 1)",
          transformStyle: "preserve-3d",
          position: "relative",
          width: "120px",
          height: "130px",
        }}
      >
        <svg
          width="120"
          height="130"
          viewBox="0 0 100 110"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={focusField === "password" && !isHovered ? "shield-glow-rapid" : ""}
          style={{
            filter: (focusField === "password" && !isHovered)
              ? undefined
              : (isHovered
                ? "drop-shadow(0 15px 25px rgba(9, 35, 79, 0.45)) drop-shadow(0 0 8px rgba(85, 199, 179, 0.25))"
                : "drop-shadow(0 10px 15px rgba(9, 35, 79, 0.35))"),
            transition: "filter 0.3s ease",
            transform: "translateZ(30px)", // Elevate slightly for depth in 3D
          }}
        >
          <defs>
            {/* Dark premium metallic plate base */}
            <linearGradient id="shield-base-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#111B30" />
              <stop offset="50%" stopColor="#0B1323" />
              <stop offset="100%" stopColor="#04070F" />
            </linearGradient>

            {/* Premium Gold metallic border gradient */}
            <linearGradient id="shield-gold-border" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#E8C98A" />
              <stop offset="25%" stopColor="#C8A46A" />
              <stop offset="50%" stopColor="#FFF2D4" />
              <stop offset="75%" stopColor="#C8A46A" />
              <stop offset="100%" stopColor="#876834" />
            </linearGradient>

            {/* Specular highlight shine that tracks the cursor */}
            <radialGradient
              id="metallic-sheen"
              cx={`${shineX}%`}
              cy={`${shineY}%`}
              r="45%"
            >
              <stop offset="0%" stopColor="rgba(255, 255, 255, 0.45)" />
              <stop offset="20%" stopColor="rgba(255, 255, 255, 0.2)" />
              <stop offset="60%" stopColor="rgba(255, 240, 210, 0.05)" />
              <stop offset="100%" stopColor="rgba(255, 255, 255, 0)" />
            </radialGradient>
          </defs>

          {/* Outer Shield Path */}
          <path
            d="M50 8 C50 8 88 18 88 18 V50 C88 78 50 100 50 100 C50 100 12 78 12 50 V18 C12 18 50 8 50 8 Z"
            fill="url(#shield-base-grad)"
            stroke="url(#shield-gold-border)"
            strokeWidth="3.5"
            strokeLinejoin="round"
          />

          {/* Inner Inset Line */}
          <path
            d="M50 16 C50 16 80 24 80 24 V48 C80 70 50 89 50 89 C50 89 20 70 20 48 V24 C20 24 50 16 50 16 Z"
            stroke="rgba(200, 164, 106, 0.25)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />

          {/* Segmented grids for security details */}
          <path
            d="M50 16 V89 M20 48 H80"
            stroke="rgba(200, 164, 106, 0.12)"
            strokeWidth="1"
          />

          {/* Visentix Logo Mark V centered inside shield */}
          <path
            d="M38 40 L50 62 L62 40"
            stroke="url(#shield-gold-border)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Dynamic Light Specular Reflection Mask Overlay */}
          <path
            d="M50 8 C50 8 88 18 88 18 V50 C88 78 50 100 50 100 C50 100 12 78 12 50 V18 C12 18 50 8 50 8 Z"
            fill="url(#metallic-sheen)"
            style={{
              mixBlendMode: "overlay",
              pointerEvents: "none",
            }}
          />
        </svg>
      </div>
    </div>
  );
}
