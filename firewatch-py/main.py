#!/usr/bin/env python3
import argparse

from firewatch.app import App

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Firewatch scene (Panda3D)')
    parser.add_argument('--fps', type=int, help='frame rate cap, 0 = uncapped; also F in the app and the Graphics tab')
    parser.add_argument('--vsync', action=argparse.BooleanOptionalAction, help='sync frames to the display refresh rate')
    args = parser.parse_args()
    App(fps=args.fps, vsync=args.vsync).run()
