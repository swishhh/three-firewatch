#!/usr/bin/env python3
"""The world editor: same renderer and graphics settings as the game, editing a world save that the
game then plays."""
import argparse

from firewatch.app import App

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Firewatch world editor (Panda3D)')
    parser.add_argument('--world', help='world save to open (default: the last one opened)')
    parser.add_argument('--fps', type=int, help='frame rate cap, 0 = uncapped, -1 = display refresh rate')
    parser.add_argument('--vsync', action=argparse.BooleanOptionalAction, help='sync frames to the display refresh rate')
    args = parser.parse_args()
    App(fps=args.fps, vsync=args.vsync, mode='editor', world=args.world).run()
