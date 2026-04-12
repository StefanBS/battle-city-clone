"""Dump raw pygame joystick/controller events for diagnosis.

Usage:
    uv run python scripts/controller_debug.py

Opens every connected joystick via BOTH the raw joystick API and the
SDL GameController API (pygame._sdl2.controller), prints static device
info, then streams every event to stdout.

Press Ctrl+C to exit.
"""

from __future__ import annotations

import sys

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller  # type: ignore
except ImportError:
    sdl_controller = None


def open_joystick(index: int) -> None:
    """Open both the raw Joystick and GameController wrapper for a device."""
    js = pygame.joystick.Joystick(index)
    js.init()
    print(
        f"  JOY  [{index}] name={js.get_name()!r} "
        f"instance_id={js.get_instance_id()} "
        f"buttons={js.get_numbuttons()} "
        f"axes={js.get_numaxes()} "
        f"hats={js.get_numhats()} "
        f"guid={js.get_guid()}"
    )
    if sdl_controller is None:
        print("  (pygame._sdl2.controller not available)")
        return
    try:
        if sdl_controller.is_controller(index):
            c = sdl_controller.Controller(index)
            c.init()
            print(f"  CTRL [{index}] opened as SDL GameController: {c.name}")
        else:
            print(f"  CTRL [{index}] NOT recognized by SDL GameController DB")
    except Exception as exc:
        print(f"  CTRL [{index}] failed to open: {exc}")


def main() -> int:
    pygame.init()
    if sdl_controller is not None:
        sdl_controller.init()
    screen = pygame.display.set_mode((320, 120))
    pygame.display.set_caption("controller_debug — press buttons; Ctrl+C to quit")
    screen.fill((20, 20, 20))
    pygame.display.flip()

    print(f"pygame {pygame.version.ver}")
    print(f"SDL {'.'.join(str(n) for n in pygame.get_sdl_version())}")
    print(f"_sdl2.controller available: {sdl_controller is not None}")
    count = pygame.joystick.get_count()
    print(f"Joystick count at startup: {count}")
    for i in range(count):
        open_joystick(i)
    print()
    print("Streaming events — press buttons/sticks on each controller.")
    print("Ctrl+C to quit.\n")

    last_poll_snapshot: str | None = None
    frame = 0
    try:
        while True:
            pygame.event.pump()
            frame += 1
            # Every ~10 frames (~100ms) poll each opened joystick and print
            # button/axis state if it changed. This bypasses the event queue
            # entirely, so if buttons register here but nothing shows up in
            # the event stream, we know SDL is dropping events.
            if frame % 10 == 0:
                parts = []
                for i in range(pygame.joystick.get_count()):
                    js = pygame.joystick.Joystick(i)
                    buttons = [
                        b for b in range(js.get_numbuttons()) if js.get_button(b)
                    ]
                    axes = [
                        f"a{a}={js.get_axis(a):+.2f}"
                        for a in range(js.get_numaxes())
                        if abs(js.get_axis(a)) > 0.2
                    ]
                    hats = [
                        f"h{h}={js.get_hat(h)}"
                        for h in range(js.get_numhats())
                        if js.get_hat(h) != (0, 0)
                    ]
                    if buttons or axes or hats:
                        parts.append(
                            f"[{i}] buttons={buttons} "
                            + " ".join(axes + hats)
                        )
                snapshot = " | ".join(parts)
                if snapshot and snapshot != last_poll_snapshot:
                    print(f"POLL {snapshot}")
                    last_poll_snapshot = snapshot
            for event in pygame.event.get():
                t = pygame.event.event_name(event.type)
                if event.type == pygame.QUIT:
                    return 0
                if event.type == pygame.JOYDEVICEADDED:
                    idx = event.device_index
                    print(f"{t} device_index={idx}")
                    open_joystick(idx)
                    continue
                if event.type == pygame.JOYDEVICEREMOVED:
                    print(f"{t} instance_id={event.instance_id}")
                    continue
                if event.type in (
                    pygame.JOYBUTTONDOWN,
                    pygame.JOYBUTTONUP,
                ):
                    print(
                        f"{t} joy={getattr(event, 'joy', '?')} "
                        f"instance_id={getattr(event, 'instance_id', '?')} "
                        f"button={event.button}"
                    )
                elif event.type == pygame.JOYAXISMOTION:
                    if abs(event.value) < 0.2:
                        continue
                    print(
                        f"{t} joy={getattr(event, 'joy', '?')} "
                        f"instance_id={getattr(event, 'instance_id', '?')} "
                        f"axis={event.axis} value={event.value:+.2f}"
                    )
                elif event.type == pygame.JOYHATMOTION:
                    print(
                        f"{t} joy={getattr(event, 'joy', '?')} "
                        f"instance_id={getattr(event, 'instance_id', '?')} "
                        f"hat={event.hat} value={event.value}"
                    )
                elif event.type in (
                    pygame.CONTROLLERBUTTONDOWN,
                    pygame.CONTROLLERBUTTONUP,
                ):
                    print(
                        f"{t} instance_id={getattr(event, 'instance_id', '?')} "
                        f"button={event.button}"
                    )
                elif event.type == pygame.CONTROLLERAXISMOTION:
                    if abs(event.value) < 0.2 * 32768:
                        continue
                    print(
                        f"{t} instance_id={getattr(event, 'instance_id', '?')} "
                        f"axis={event.axis} value={event.value}"
                    )
                elif event.type in (
                    pygame.CONTROLLERDEVICEADDED,
                    pygame.CONTROLLERDEVICEREMOVED,
                    pygame.CONTROLLERDEVICEREMAPPED,
                ):
                    print(f"{t} {event.__dict__}")
            pygame.time.wait(10)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
