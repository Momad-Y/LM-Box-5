#!/bin/bash
# Cleanup script to remove unnecessary files before publishing to GitHub

echo "Starting cleanup process for LM Box 5 project..."

# Remove test files
echo "Removing test files..."
rm -f test_components.py
rm -f test_dino.py
rm -f test_dino_gui.py
rm -f test_fullscreen_dino.py
rm -f test_with_debug.py
rm -f dino_test_output.log

# Remove duplicate/backup files
echo "Removing duplicate and backup files..."
rm -f gui/dino_game_fixed.py
rm -f gui/gui.py.bak
rm -f dinosaur_game_main/main.py.bak

# Remove debug files
echo "Removing debug files..."
rm -f main_debug.py

# Remove dinosaur_game_main directory since it's been integrated into gui/dino_game.py

# Remove __pycache__ directories
echo "Cleaning Python cache directories..."
find . -type d -name "__pycache__" -exec rm -rf {} +

# Print completion message
echo "Cleanup complete! The project is now ready for GitHub."
echo "You may want to review the changes before committing them."
