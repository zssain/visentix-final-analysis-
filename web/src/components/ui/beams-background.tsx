import { useEffect, useRef } from "react";
import { motion } from "motion/react";
import { cn } from "../../lib/utils";

interface AnimatedGradientBackgroundProps {
    className?: string;
    children?: React.ReactNode;
    intensity?: "subtle" | "medium" | "strong";
}

interface Beam {
    x: number;
    y: number;
    width: number;
    length: number;
    angle: number;
    speed: number;
    opacity: number;
    hue: number;
    pulse: number;
    pulseSpeed: number;
}

function createBeam(width: number, height: number): Beam {
    const angle = -35 + Math.random() * 10;
    // Brand hues: Teal (170), Gold (38), Executive Blue/Cyan (205)
    const hues = [170, 38, 205];
    const baseHue = hues[Math.floor(Math.random() * hues.length)];
    return {
        x: Math.random() * width * 1.5 - width * 0.25,
        y: Math.random() * height * 1.5 - height * 0.25,
        width: 30 + Math.random() * 60,
        length: height * 2.5,
        angle: angle,
        speed: 0.6 + Math.random() * 1.2,
        opacity: 0.08 + Math.random() * 0.12,
        hue: baseHue + (Math.random() - 0.5) * 10,
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.02 + Math.random() * 0.03,
    };
}

export function BeamsBackground({
    className,
    children,
    intensity = "strong",
}: AnimatedGradientBackgroundProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const beamsRef = useRef<Beam[]>([]);
    const animationFrameRef = useRef<number>(0);
    const MINIMUM_BEAMS = 20;

    const opacityMap = {
        subtle: 0.5,
        medium: 0.75,
        strong: 1.0,
    };

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const updateCanvasSize = () => {
            const dpr = window.devicePixelRatio || 1;
            const parent = canvas.parentElement;
            const width = parent ? parent.clientWidth : window.innerWidth;
            const height = parent ? parent.clientHeight : window.innerHeight;

            canvas.width = width * dpr;
            canvas.height = height * dpr;
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
            ctx.scale(dpr, dpr);

            const totalBeams = MINIMUM_BEAMS * 1.5;
            beamsRef.current = Array.from({ length: totalBeams }, () =>
                createBeam(width, height)
            );
        };

        updateCanvasSize();
        window.addEventListener("resize", updateCanvasSize);

        function resetBeam(beam: Beam, index: number) {
            if (!canvas) return beam;
            
            const column = index % 3;
            const spacing = canvas.width / (window.devicePixelRatio || 1) / 3;

            beam.y = (canvas.height / (window.devicePixelRatio || 1)) + 100;
            beam.x =
                column * spacing +
                spacing / 2 +
                (Math.random() - 0.5) * spacing * 0.5;
            beam.width = 80 + Math.random() * 100;
            beam.speed = 0.4 + Math.random() * 0.5;
            
            const hues = [170, 38, 205];
            beam.hue = hues[index % hues.length] + (Math.random() - 0.5) * 10;
            beam.opacity = 0.12 + Math.random() * 0.08;
            return beam;
        }

        function drawBeam(ctx: CanvasRenderingContext2D, beam: Beam) {
            ctx.save();
            ctx.translate(beam.x, beam.y);
            ctx.rotate((beam.angle * Math.PI) / 180);

            // Calculate pulsing opacity
            const pulsingOpacity =
                beam.opacity *
                (0.8 + Math.sin(beam.pulse) * 0.2) *
                opacityMap[intensity];

            const gradient = ctx.createLinearGradient(0, 0, 0, beam.length);

            // Enhanced gradient with multiple color stops
            gradient.addColorStop(0, `hsla(${beam.hue}, 85%, 65%, 0)`);
            gradient.addColorStop(
                0.1,
                `hsla(${beam.hue}, 85%, 65%, ${pulsingOpacity * 0.4})`
            );
            gradient.addColorStop(
                0.4,
                `hsla(${beam.hue}, 85%, 65%, ${pulsingOpacity})`
            );
            gradient.addColorStop(
                0.6,
                `hsla(${beam.hue}, 85%, 65%, ${pulsingOpacity})`
            );
            gradient.addColorStop(
                0.9,
                `hsla(${beam.hue}, 85%, 65%, ${pulsingOpacity * 0.4})`
            );
            gradient.addColorStop(1, `hsla(${beam.hue}, 85%, 65%, 0)`);

            ctx.fillStyle = gradient;
            ctx.fillRect(-beam.width / 2, 0, beam.width, beam.length);
            ctx.restore();
        }

        function animate() {
            if (!canvas || !ctx) return;

            const width = canvas.width / (window.devicePixelRatio || 1);
            const height = canvas.height / (window.devicePixelRatio || 1);

            ctx.clearRect(0, 0, width, height);
            ctx.filter = "blur(35px)";

            beamsRef.current.forEach((beam, index) => {
                beam.y -= beam.speed;
                beam.pulse += beam.pulseSpeed;

                // Reset beam when it goes off screen
                if (beam.y + beam.length < -100) {
                    resetBeam(beam, index);
                }

                drawBeam(ctx, beam);
            });

            animationFrameRef.current = requestAnimationFrame(animate);
        }

        animate();

        return () => {
            window.removeEventListener("resize", updateCanvasSize);
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [intensity]);

    return (
        <div
            className={cn(
                "relative overflow-hidden bg-neutral-950 w-full h-full",
                className
            )}
            style={{
                position: "relative",
                overflow: "hidden",
                width: "100%",
                height: "100%",
                backgroundColor: "transparent",
            }}
        >
            <canvas
                ref={canvasRef}
                className="absolute inset-0"
                style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: "100%",
                    filter: "blur(15px)",
                    pointerEvents: "none",
                }}
            />

            <motion.div
                className="absolute inset-0 bg-neutral-950/5"
                animate={{
                    opacity: [0.03, 0.1, 0.03],
                }}
                transition={{
                    duration: 10,
                    ease: "easeInOut",
                    repeat: Number.POSITIVE_INFINITY,
                }}
                style={{
                    position: "absolute",
                    inset: 0,
                    backgroundColor: "rgba(9, 35, 79, 0.08)",
                    backdropFilter: "blur(40px)",
                    pointerEvents: "none",
                }}
            />

            <div style={{ position: "relative", zIndex: 10, width: "100%", height: "100%" }}>
                {children}
            </div>
        </div>
    );
}
