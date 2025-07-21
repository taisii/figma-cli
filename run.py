#!/usr/bin/env python

import argparse
import dotenv
from src.main_controller import MainController

def main():
    """アプリケーションのメインエントリーポイント"""
    dotenv.load_dotenv() # Load environment variables at the very beginning
    parser = argparse.ArgumentParser(description="Figma to Research Outline CLI")
    parser.add_argument("--strategy", action="store_true", help="Run the strategy generation cycle.")
    args = parser.parse_args()

    try:
        controller = MainController()
        if args.strategy:
            controller.execute_strategy_cycle()
        else:
            controller.run()
    except Exception as e:
        import traceback
        print(f"An error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
