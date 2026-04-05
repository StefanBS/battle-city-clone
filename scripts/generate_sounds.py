"""Generate retro 8-bit WAV sound effects for Battle City clone.

All files: mono, 22050 Hz, 16-bit PCM.
Output directory: assets/sounds/
"""

import math
import os
import random
import struct
import wave

SAMPLE_RATE = 22050
MAX_AMPLITUDE = 32767
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "assets", "sounds"
)


def write_wav(filename: str, samples: list[float]) -> None:
    """Write a list of float samples (range -1.0 to 1.0) to a 16-bit mono WAV file."""
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        packed = struct.pack(
            f"<{len(samples)}h",
            *(int(s * MAX_AMPLITUDE) for s in samples),
        )
        wf.writeframes(packed)
    print(f"  wrote {path} ({len(samples)} samples, {len(samples) / SAMPLE_RATE:.3f}s)")


def square_wave(freq: float, t: float) -> float:
    """Return a square wave sample at time t for the given frequency."""
    return 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0


def generate_shoot() -> None:
    """Short square wave burst with descending frequency (800→200 Hz), ~0.1s."""
    duration = 0.1
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = i / num_samples
        freq = 800 - (800 - 200) * progress  # linear descent 800→200 Hz
        amplitude = 1.0 - progress * 0.5  # slight fade
        samples.append(square_wave(freq, t) * amplitude)
    write_wav("shoot.wav", samples)


def generate_brick_hit() -> None:
    """White noise burst with decay, ~0.08s."""
    duration = 0.08
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    rng = random.Random(42)
    for i in range(num_samples):
        progress = i / num_samples
        decay = math.exp(-progress * 8)  # exponential decay
        noise = rng.uniform(-1.0, 1.0)
        samples.append(noise * decay)
    write_wav("brick_hit.wav", samples)


def generate_explosion() -> None:
    """Longer noise burst with decay, ~0.3s."""
    duration = 0.3
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    rng = random.Random(7)
    for i in range(num_samples):
        progress = i / num_samples
        decay = math.exp(-progress * 5)  # slower decay for longer rumble
        noise = rng.uniform(-1.0, 1.0)
        samples.append(noise * decay)
    write_wav("explosion.wav", samples)


def generate_powerup() -> None:
    """Ascending 3-note chime: C5=523Hz, E5=659Hz, G5=784Hz, each ~0.08s."""
    note_duration = 0.08
    note_samples = int(SAMPLE_RATE * note_duration)
    freqs = [523.0, 659.0, 784.0]
    samples = []
    for freq in freqs:
        for i in range(note_samples):
            t = i / SAMPLE_RATE
            progress = i / note_samples
            amplitude = 1.0 - progress * 0.4  # gentle fade per note
            samples.append(square_wave(freq, t) * amplitude)
    write_wav("powerup.wav", samples)


def generate_game_over() -> None:
    """Descending frequency sweep (400→100 Hz), ~0.8s."""
    duration = 0.8
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = i / num_samples
        freq = 400 - (400 - 100) * progress  # linear descent 400→100 Hz
        amplitude = 1.0 - progress * 0.6  # fade over time
        samples.append(square_wave(freq, t) * amplitude)
    write_wav("game_over.wav", samples)


def generate_engine() -> None:
    """Low-frequency square wave buzz for tank engine, ~0.3s seamless loop."""
    duration = 0.3
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        freq = 70 + 10 * math.sin(2 * math.pi * 3 * t)
        amplitude = 0.6
        samples.append(square_wave(freq, t) * amplitude)
    write_wav("engine.wav", samples)


def generate_bullet_hit_bullet() -> None:
    """Short metallic ping, ~0.05s."""
    duration = 0.05
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = i / num_samples
        decay = math.exp(-progress * 12)
        samples.append(square_wave(1200, t) * decay)
    write_wav("bullet_hit_bullet.wav", samples)


def _generate_fanfare(
    filename: str,
    freqs: list[float],
    note_duration: float = 0.4,
    gap_duration: float = 0.04,
    fade: float = 0.3,
) -> None:
    """Generate a multi-note square wave fanfare."""
    note_samples = int(SAMPLE_RATE * note_duration)
    gap_samples = int(SAMPLE_RATE * gap_duration)
    samples = []
    for freq in freqs:
        for i in range(note_samples):
            t = i / SAMPLE_RATE
            progress = i / note_samples
            amplitude = 1.0 - progress * fade
            samples.append(square_wave(freq, t) * amplitude)
        samples.extend([0.0] * gap_samples)
    write_wav(filename, samples)


def generate_stage_start() -> None:
    """Ascending 4-note fanfare (C4-E4-G4-C5), ~2.0s."""
    _generate_fanfare("stage_start.wav", [261.6, 329.6, 392.0, 523.3])


def generate_victory() -> None:
    """Triumphant 3-note ascending chord (G4-B4-D5), ~1.5s."""
    _generate_fanfare("victory.wav", [392.0, 493.9, 587.3])


def generate_menu_select() -> None:
    """Quick tick/blip, ~0.03s."""
    duration = 0.03
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        progress = i / num_samples
        amplitude = 1.0 - progress * 0.5
        samples.append(square_wave(800, t) * amplitude)
    write_wav("menu_select.wav", samples)


def generate_ice_slide() -> None:
    """White noise burst with decay, lower freq than brick_hit, ~0.15s."""
    duration = 0.15
    num_samples = int(SAMPLE_RATE * duration)
    samples = []
    rng = random.Random(99)
    for i in range(num_samples):
        progress = i / num_samples
        decay = math.exp(-progress * 6)
        noise = rng.uniform(-1.0, 1.0)
        raw = noise * decay
        if samples:
            raw = 0.6 * raw + 0.4 * samples[-1]
        samples.append(raw)
    write_wav("ice_slide.wav", samples)


def generate_powerup_spawn() -> None:
    """Short blip + silence for looping blink sound.

    Total duration = POWERUP_BLINK_INTERVAL * 2 = 0.3s.
    """
    total_duration = 0.3
    blip_duration = 0.05
    blip_samples = int(SAMPLE_RATE * blip_duration)
    total_samples = int(SAMPLE_RATE * total_duration)
    samples = []
    for i in range(blip_samples):
        t = i / SAMPLE_RATE
        progress = i / blip_samples
        amplitude = 1.0 - progress * 0.5
        samples.append(square_wave(1000, t) * amplitude)
    samples.extend([0.0] * (total_samples - blip_samples))
    write_wav("powerup_spawn.wav", samples)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating sounds in {OUTPUT_DIR}/")
    generate_shoot()
    generate_brick_hit()
    generate_explosion()
    generate_powerup()
    generate_game_over()
    generate_engine()
    generate_bullet_hit_bullet()
    generate_stage_start()
    generate_victory()
    generate_menu_select()
    generate_ice_slide()
    generate_powerup_spawn()
    print("Done.")


if __name__ == "__main__":
    main()
