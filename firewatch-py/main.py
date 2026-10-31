#!/usr/bin/env python3
"""The game: walk the active world in first person (or another save with --world)."""
import argparse

from firewatch.app import App

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Firewatch scene (Panda3D)')
    parser.add_argument('--world', help='world save to play (default: the one last opened in the editor)')
    parser.add_argument('--fps', type=int, help='frame rate cap, 0 = uncapped, -1 = display refresh rate; '
                                                'also F in the app and the Graphics tab')
    parser.add_argument('--vsync', action=argparse.BooleanOptionalAction, help='sync frames to the display refresh rate')
    args = parser.parse_args()
    App(fps=args.fps, vsync=args.vsync, mode='game', world=args.world).run()
