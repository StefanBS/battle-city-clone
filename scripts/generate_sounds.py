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
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds")


def write_wav(filename: str, samples: list[float]) -> None:
    """Write a list of float samples (range -1.0 to 1.0) to a 16-bit mono WAV file."""
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        packed = struct.pack(f"<{len(samples)}h", *(int(s * MAX_AMPLITUDE) for s in samples))
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


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating sounds in {OUTPUT_DIR}/")
    generate_shoot()
    generate_brick_hit()
    generate_explosion()
    generate_powerup()
    generate_game_over()
    print("Done.")


if __name__ == "__main__":
    main()
