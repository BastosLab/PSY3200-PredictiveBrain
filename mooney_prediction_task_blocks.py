#!/usr/bin/env python3
"""
Mooney Prediction Task - Block-Based Implementation
====================================================

Implements the predictive brain experiment with block structure:
- Each block: 49 trials (pre 24 + reveal (load prior) 1 + post 24)
- 10 blocks with a new target image/sentence per block
- Target stimuli oversampled to test predictive coding

Visual session: two-tone ("Mooney") images. The reveal (load prior) shows
the original photo, then the two-tone again.
Audio session: sine-wave speech. The reveal (load prior) plays the clear sentence,
then the sine-wave version again.
The stimuli in stimuli/twotone, images_clear, sws and speech_clear are made
by make_stimuli.py.

Requirements:
    - pillow (PIL)
    - numpy
    - pygame (for audio playback; pygame-ce works too and installs on newer Pythons)

Install: pip install pillow numpy pygame-ce

Usage:
    python mooney_prediction_task_blocks.py
    python mooney_prediction_task_blocks.py --participant P01 --modality visual
    python mooney_prediction_task_blocks.py --autopilot --speed 50 --modality audio   # testing

Keys: → = YES, ← = NO, SPACE = continue, ESC = quit (asks first).
Every trial is saved the moment it ends, so closing the window loses nothing.
"""

import os
import re
import sys
import csv
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image, ImageTk
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
import tkinter as tk
from tkinter import messagebox

N_ITEMS = 12                # 12 images and 12 sentences
IMAGE_SIZE = 300            # pixels on screen
REVEAL_IMAGE_S = 3.0        # original photo, then two-tone, in the reveal (load prior)
REVEAL_GAP_S = 0.5          # clear sentence -> gap -> sine-wave speech
REVEAL_TITLE = "Reveal (load prior)"

FIELDNAMES = [
    'participant_id', 'modality', 'seed', 'n_blocks', 'block', 'trial_number',
    'trial_type', 'target_index', 'stimulus_index', 'stimulus_file', 'condition',
    'response', 'recognized', 'reaction_time_ms', 'timestamp',
]


class MooneyPredictionTask:
    """Block-based Mooney prediction task implementation."""

    def __init__(self, stimuli_dir: Path, data_dir: Path, n_blocks: int = 10,
                 target_reps: int = 8, n_fillers: int = 4, filler_reps: int = 4,
                 seed: Optional[int] = None):
        self.stimuli_dir = Path(stimuli_dir)
        self.data_dir = Path(data_dir)
        if not 1 <= n_blocks <= N_ITEMS:
            raise ValueError(f"n_blocks must be 1-{N_ITEMS} (each block needs a new target)")
        self.n_blocks = n_blocks
        self.target_reps = target_reps
        self.n_fillers = n_fillers
        self.filler_reps = filler_reps

        pygame.mixer.init()

        self.images = self._load_images('twotone')          # degraded (two-tone) versions
        self.originals = self._load_images('images_clear')  # shown during the reveal
        self.sounds = self._load_sounds('sws')              # sine-wave speech
        self.clear_sounds = self._load_sounds('speech_clear')

        print(f"✓ Loaded {len(self.images)} images")
        print(f"✓ Loaded {len(self.sounds)} sounds")

        # Session tracking
        self.participant_id = None
        self.modality = None
        self.session_data = []
        self.current_trial = 0
        self.current_block = 0
        self.trial_start_time = None
        self.data_file = None
        self.data_path = None
        self.revealed = set()           # items whose original has been shown so far

        # All shuffling uses this seed, so a session can be rebuilt from its CSV
        self.seed = seed if seed is not None else random.SystemRandom().randrange(2 ** 32)
        self.rng = random.Random(self.seed)

        self.item_indices = list(range(N_ITEMS))

    def _load_images(self, folder: str) -> List[np.ndarray]:
        """Load the images in stimuli/<folder>/img01.png ... img12.png."""
        images = []
        for i in range(1, N_ITEMS + 1):
            img_path = self.stimuli_dir / folder / f"img{i:02d}.png"
            img = Image.open(img_path).convert('L')
            images.append(np.array(img))
        return images

    def _load_sounds(self, folder: str) -> List[pygame.mixer.Sound]:
        """Load the sounds in stimuli/<folder>/sent01.wav ... sent12.wav."""
        return [pygame.mixer.Sound(str(self.stimuli_dir / folder / f"sent{i:02d}.wav"))
                for i in range(1, N_ITEMS + 1)]

    def play_sound(self, sound_index: int, clear: bool = False) -> float:
        """Start a sound and return at once (it plays in the background). Returns its length in s."""
        sound = (self.clear_sounds if clear else self.sounds)[sound_index]
        pygame.mixer.stop()
        sound.play()
        return sound.get_length()

    def stimulus_name(self, index: int) -> str:
        return f"{'img' if self.modality == 'visual' else 'sent'}{index + 1:02d}"

    def trials_per_block(self) -> int:
        return 2 * (self.target_reps + self.n_fillers * self.filler_reps) + 1

    def generate_block_sequence(self, target_idx: int) -> dict:
        """Generate pre/reveal/post sequences for a block."""
        # 4 random other items ("fillers"), shown in both phases of this block
        other_items = [i for i in self.item_indices if i != target_idx]
        fillers = self.rng.sample(other_items, self.n_fillers)

        # Pre and post: the same 24 trials (8 target + 4 fillers x 4),
        # in a new random order each time
        phase_items = [target_idx] * self.target_reps
        for item in fillers:
            phase_items.extend([item] * self.filler_reps)

        pre_sequence = phase_items[:]
        self.rng.shuffle(pre_sequence)
        post_sequence = phase_items[:]
        self.rng.shuffle(post_sequence)

        return {
            'pre': pre_sequence,
            'reveal': target_idx,
            'post': post_sequence,
            'fillers': fillers,
        }

    def open_data_file(self) -> None:
        """Create the CSV at the start of the session; each trial is added as it ends."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_path = self.data_dir / f"mooney_{self.participant_id}_{self.modality}_{timestamp}.csv"
        self.data_file = open(self.data_path, 'w', newline='')
        self.writer = csv.DictWriter(self.data_file, fieldnames=FIELDNAMES)
        self.writer.writeheader()
        self._sync()
        print(f"✓ Saving data to {self.data_path}")

    def _sync(self) -> None:
        self.data_file.flush()
        os.fsync(self.data_file.fileno())

    def save_session(self) -> None:
        """Close the data file (every trial is already on disk)."""
        if self.data_file and not self.data_file.closed:
            self.data_file.close()
            print(f"✓ Session data saved to {self.data_path}")

    def condition_of(self, stimulus_idx: int, target_idx: int) -> str:
        """target = this block's target; filler_new / filler_old = original not yet / already shown."""
        if stimulus_idx == target_idx:
            return 'target'
        return 'filler_old' if stimulus_idx in self.revealed else 'filler_new'

    def log_trial(self, block: int, trial_type: str, stimulus_idx: int, target_idx: int,
                  response: Optional[str], reaction_time: Optional[float]) -> None:
        """Log a trial and write it to disk immediately."""
        record = {
            'participant_id': self.participant_id,
            'modality': self.modality,
            'seed': self.seed,
            'n_blocks': self.n_blocks,
            'block': block,
            'trial_number': self.current_trial,
            'trial_type': trial_type,
            'target_index': target_idx + 1,
            'stimulus_index': stimulus_idx + 1,     # 1-12, matches img01 / sent01
            'stimulus_file': self.stimulus_name(stimulus_idx),
            'condition': self.condition_of(stimulus_idx, target_idx),
            'response': response or 'NA',
            'recognized': {'yes': 1, 'no': 0}.get(response, 'NA'),
            'reaction_time_ms': 'NA' if reaction_time is None else round(reaction_time * 1000, 2),
            'timestamp': datetime.now().isoformat(),
        }
        self.session_data.append(record)
        self.writer.writerow(record)
        self._sync()


class MooneyGUI:
    """GUI for block-based Mooney task."""

    def __init__(self, task: MooneyPredictionTask, autopilot: bool = False, speed: float = 1.0):
        self.task = task
        self.autopilot = autopilot
        self.speed = speed if autopilot else 1.0
        self.auto_rng = random.Random()
        self.root = tk.Tk()
        self.root.title("Mooney Prediction Task - Block Design")
        self.root.minsize(600, 500)
        self.root.configure(bg='white')
        self.root.bind('<Escape>', lambda e: self.request_quit())
        self.root.protocol('WM_DELETE_WINDOW', self.request_quit)

        self.response = None
        self.quit_requested = False
        self.show_menu()

    def show_menu(self) -> None:
        """Show main menu."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(
            frame, text="Mooney Prediction Task",
            font=("Helvetica", 20, "bold"), bg='white', fg='black'
        ).pack(pady=20)

        tk.Label(
            frame, text=f"Block-Based Design\n({self.task.n_blocks} blocks × {self.task.trials_per_block()} trials)",
            font=("Helvetica", 12), bg='white', fg='gray'
        ).pack(pady=10)

        tk.Label(
            frame, text="Select task modality:",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=10)

        button_frame = tk.Frame(frame, bg='white')
        button_frame.pack(pady=20)

        tk.Button(
            button_frame, text="VISUAL",
            command=lambda: self.start_task('visual'),
            width=15, font=("Helvetica", 11), bg='lightblue', activebackground='skyblue'
        ).pack(side='left', padx=10)

        tk.Button(
            button_frame, text="AUDIO",
            command=lambda: self.start_task('audio'),
            width=15, font=("Helvetica", 11), bg='lightgreen', activebackground='lightseagreen'
        ).pack(side='left', padx=10)

    def start_task(self, modality: str) -> None:
        """Ask for the participant ID, then start the session."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(
            frame, text="Enter Participant ID:",
            font=("Helvetica", 14), bg='white', fg='black'
        ).pack(pady=20)

        entry = tk.Entry(frame, font=("Helvetica", 12), width=20)
        entry.pack(pady=10)
        entry.focus()

        start = lambda: self.begin_session(entry.get(), modality)
        tk.Button(frame, text="Start", command=start, width=12, bg='gold', activebackground='orange').pack(pady=20)
        entry.bind('<Return>', lambda e: start())

    def begin_session(self, participant_id: str, modality: str) -> None:
        # Only letters, digits, - and _ (the ID becomes part of the file name)
        pid = re.sub(r'[^A-Za-z0-9_-]', '', participant_id)
        if not pid:
            messagebox.showwarning("Error", "Please enter a participant ID (letters, numbers, - or _)")
            return
        self.task.participant_id = pid
        self.task.modality = modality
        self.task.session_data = []
        self.task.open_data_file()
        self.root.focus_force()
        self.run_blocks()

    def run_blocks(self) -> None:
        """Run all blocks."""
        num_blocks = self.task.n_blocks

        # A different target item in every block
        target_indices = self.task.rng.sample(self.task.item_indices, num_blocks)

        for block_num in range(num_blocks):
            self.task.current_block = block_num + 1
            target = target_indices[block_num]
            block_sequence = self.task.generate_block_sequence(target)

            self.show_block_intro(block_num + 1, num_blocks)
            if self.quit_requested:
                break

            # Pre phase
            if not self.run_phase(block_num + 1, 'pre', block_sequence['pre'], target):
                break

            # Reveal (load prior): the target's clear original, then its degraded version
            self.task.current_trial += 1
            self.run_reveal(target)
            if self.quit_requested:
                break
            self.task.log_trial(block_num + 1, 'reveal', target, target, None, None)
            self.task.revealed.add(target)

            # Post phase
            if not self.run_phase(block_num + 1, 'post', block_sequence['post'], target):
                break

        self.show_completion()

    def run_phase(self, block: int, trial_type: str, sequence: List[int], target: int) -> bool:
        """Run the pre or post trials of a block. Returns False if the participant quit."""
        for idx in sequence:
            self.task.current_trial += 1
            if self.task.modality == 'visual':
                response, rt = self.run_visual_trial(idx)
            else:
                response, rt = self.run_audio_trial(idx)

            if response is None:
                return False
            self.task.log_trial(block, trial_type, idx, target, response, rt)
        return True

    def show_block_intro(self, block_num: int, total_blocks: int) -> None:
        """Break screen before every block, showing its number. SPACE starts the block."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(
            frame, text=f"Block {block_num - 1} of {total_blocks} done. Take a short break."
            if block_num > 1 else "Get ready.",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=(60, 0))

        tk.Label(
            frame, text=f"Block {block_num} of {total_blocks}",
            font=("Helvetica", 18, "bold"), bg='white', fg='blue'
        ).pack(pady=40)

        tk.Label(
            frame, text=f"Press SPACE when you are ready to start block {block_num}.",
            font=("Helvetica", 12), bg='white', fg='gray'
        ).pack(pady=20)

        self.response = None
        def on_space(event):
            self.response = 'continue'

        self.root.bind('<space>', on_space)
        self.wait_for_response(['continue'])
        self.root.unbind('<space>')

    def bind_yes_no(self) -> None:
        def on_key(event):
            if event.keysym == 'Left':
                self.response = 'no'
            elif event.keysym == 'Right':
                self.response = 'yes'

        self.root.bind('<Left>', on_key)
        self.root.bind('<Right>', on_key)

    def unbind_yes_no(self) -> None:
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')

    def show_image(self, img: np.ndarray, text: str, title: Optional[str] = None) -> None:
        self.clear()
        img_pil = Image.fromarray(img).resize((IMAGE_SIZE, IMAGE_SIZE))
        photo = ImageTk.PhotoImage(img_pil)

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=title or f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        img_label = tk.Label(frame, image=photo, bg='white')
        img_label.image = photo
        img_label.pack(pady=20)

        tk.Label(
            frame, text=text,
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=10)

    def run_visual_trial(self, img_idx: int) -> Tuple[Optional[str], float]:
        """Run a visual trial."""
        self.show_image(self.task.images[img_idx],
                        "Could you tell what is in the picture?\n\nNO (←)          YES (→)")
        self.response = None
        self.bind_yes_no()
        self.root.update()                      # draw the image before starting the clock
        self.task.trial_start_time = time.perf_counter()

        response = self.wait_for_response(['yes', 'no'])

        rt = time.perf_counter() - self.task.trial_start_time
        self.unbind_yes_no()
        return response, rt

    def run_audio_trial(self, snd_idx: int) -> Tuple[Optional[str], float]:
        """Run an audio trial. The answer can be given while the sound is still playing."""
        self.clear()

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        tk.Label(
            frame, text="Playing audio...\n\nCould you understand the words?\n\nNO (←)          YES (→)",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=30)

        self.response = None
        self.bind_yes_no()
        self.root.update()
        self.task.play_sound(snd_idx)           # returns at once, so the window stays responsive
        self.task.trial_start_time = time.perf_counter()

        response = self.wait_for_response(['yes', 'no'])

        rt = time.perf_counter() - self.task.trial_start_time
        pygame.mixer.stop()
        self.unbind_yes_no()
        return response, rt

    def run_reveal(self, target: int) -> None:
        """Show (or play) the target's clear original, then its degraded version. No response."""
        if self.task.modality == 'visual':
            self.show_image(self.task.originals[target], "Here is the original picture.", REVEAL_TITLE)
            self.pause(REVEAL_IMAGE_S)
            self.show_image(self.task.images[target], "...and here is its black-and-white version.", REVEAL_TITLE)
            self.pause(REVEAL_IMAGE_S)
        else:
            self.clear()
            frame = tk.Frame(self.root, bg='white')
            frame.pack(expand=True, fill='both')
            tk.Label(frame, text=REVEAL_TITLE, font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)
            tk.Label(
                frame, text="Listen carefully:\n\nfirst the clear recording,\nthen the strange version.",
                font=("Helvetica", 14), bg='white', fg='black'
            ).pack(pady=60)
            self.root.update()
            self.pause(self.task.play_sound(target, clear=True) + REVEAL_GAP_S)
            self.pause(self.task.play_sound(target))
            pygame.mixer.stop()

    def wait_for_response(self, choices: List[str]) -> Optional[str]:
        """Keep the window running until a key sets self.response. Returns None if the participant quit."""
        if self.autopilot:
            choice = self.auto_rng.choice(choices)
            delay_ms = int(self.auto_rng.uniform(300, 1500) / self.speed)
            self.root.after(delay_ms, lambda: setattr(self, 'response', choice))
        while self.response is None and not self.quit_requested:
            self.root.update()
            time.sleep(0.005)
        return None if self.quit_requested else self.response

    def pause(self, seconds: float) -> None:
        """Wait while keeping the window responsive."""
        end = time.perf_counter() + seconds / self.speed
        while time.perf_counter() < end and not self.quit_requested:
            self.root.update()
            time.sleep(0.005)

    def request_quit(self) -> None:
        """ESC or the window's close button."""
        if self.task.data_file is None or self.task.data_file.closed:   # not started, or finished
            self.root.destroy()
        elif messagebox.askyesno("Quit", "Quit the experiment?\n\nEverything up to now is already saved."):
            self.quit_requested = True
            pygame.mixer.stop()

    def show_completion(self) -> None:
        """Show completion screen."""
        self.clear()
        self.task.save_session()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text="Session ended early" if self.quit_requested else "Experiment Complete!",
                font=("Helvetica", 18, "bold"), bg='white', fg='green').pack(pady=30)

        tk.Label(
            frame,
            text=f"Participant: {self.task.participant_id}\nModality: {self.task.modality.upper()}\nTrials Completed: {len(self.task.session_data)}"
                 f"\n\nYour data file:\n{self.task.data_path}",
            font=("Helvetica", 12), bg='white', fg='black', wraplength=560
        ).pack(pady=20)

        tk.Label(
            frame, text="Thank you for participating!",
            font=("Helvetica", 11), bg='white', fg='gray'
        ).pack(pady=20)

        tk.Button(frame, text="Close", command=self.root.destroy, width=12, bg='lightcoral', activebackground='salmon').pack(pady=20)
        if self.autopilot:
            self.root.after(300, self.root.destroy)

    def clear(self) -> None:
        """Clear all widgets."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def run(self) -> None:
        """Start GUI."""
        self.root.mainloop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Mooney prediction task")
    parser.add_argument('--participant', help="participant ID (with --modality, skips the menu)")
    parser.add_argument('--modality', choices=['visual', 'audio'])
    parser.add_argument('--blocks', type=int, default=10, help="number of blocks (default 10)")
    parser.add_argument('--target-reps', type=int, default=8, help="target trials per phase (default 8)")
    parser.add_argument('--filler-reps', type=int, default=4, help="trials per filler per phase (default 4)")
    parser.add_argument('--data-dir', default=str(Path.home() / "mooney_data"))
    parser.add_argument('--seed', type=int, help="fix the random order (default: new every session)")
    parser.add_argument('--autopilot', action='store_true', help="answer randomly, for testing")
    parser.add_argument('--speed', type=float, default=1.0, help="autopilot only: run this many times faster")
    args = parser.parse_args()
    if args.autopilot and not args.modality:
        parser.error("--autopilot needs --modality")

    script_dir = Path(__file__).parent
    try:
        task = MooneyPredictionTask(script_dir / "stimuli", Path(args.data_dir), n_blocks=args.blocks,
                                    target_reps=args.target_reps, filler_reps=args.filler_reps,
                                    seed=args.seed)
        gui = MooneyGUI(task, autopilot=args.autopilot, speed=args.speed)
        if args.modality and (args.participant or args.autopilot):
            gui.root.after(100, lambda: gui.begin_session(args.participant or 'autopilot', args.modality))
        gui.run()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start task:\n{e}")
        raise


if __name__ == '__main__':
    main()
