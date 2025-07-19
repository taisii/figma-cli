#!/usr/bin/env python

from src.main_controller import MainController

def main():
    """アプリケーションのメインエントリーポイント"""
    try:
        controller = MainController()
        controller.run()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
