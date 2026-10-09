"""Backward-compatible database seeder. Run: python seed.py"""
from setup import seed_demo

if __name__ == "__main__":
    seed_demo(reset=True)
