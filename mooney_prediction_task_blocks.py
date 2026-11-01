#!/usr/bin/env python3
"""
Mooney Prediction Task - Block-Based Implementation
====================================================

Implements the predictive brain experiment with block structure:
- Each block: 52 trials (pre-disambiguation 24 + disambiguation 2 + post-disambiguation 25)
- 10 blocks with unique target images/audios per block
- Target stimuli oversampled to test predictive coding

Requirements:
    - pillow (PIL)
    - numpy
    - pygame (for audio playback)

Install: pip install pillow numpy pygame

Usage:
    python mooney_prediction_task_blocks.py
"""

import os
import sys
import csv
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image
import pygame
import tkinter as tk
from tkinter import messagebox, filedialog


class MooneyPredictionTask:
    """Block-based Mooney prediction task implementation."""

    def __init__(self, images_dir: Path, sounds_dir: Path):
        self.images_dir = Path(images_dir)
        self.sounds_dir = Path(sounds_dir)

        pygame.mixer.init()

        self.images = self._load_images()
        self.sounds = self._load_sounds()

        if len(self.images) < 10:
            raise ValueError(f"Need at least 10 images, found {len(self.images)}")
        if len(self.sounds) < 10:
            raise ValueError(f"Need at least 10 sounds, found {len(self.sounds)}")

        print(f"✓ Loaded {len(self.images)} images")
        print(f"✓ Loaded {len(self.sounds)} sounds")

        # Session tracking
        self.participant_id = None
        self.modality = None
        self.session_data = []
        self.current_trial = 0
        self.current_block = 0
        self.trial_start_time = None

        # Available stimuli (will be shuffled for each block)
        self.image_indices = list(range(len(self.images)))
        self.sound_indices = list(range(len(self.sounds)))

    def _load_images(self) -> List[np.ndarray]:
        """Load and preprocess Mooney images."""
        images = []
        for i in range(1, 20):
            img_path = self.images_dir / f"{i}.jpg"
            if img_path.exists():
                try:
                    img = Image.open(img_path)
                    img = img.convert('L')
                    img = img.resize((512, 512))
                    images.append(np.array(img))
                except Exception as e:
                    print(f"Warning: Could not load {img_path}: {e}")
            else:
                break
        return images

    def _load_sounds(self) -> List[str]:
        """Load sound file paths."""
        sounds = []
        for i in range(1, 40):
            snd_path = self.sounds_dir / f"{i}.mp3"
            if snd_path.exists():
                sounds.append(str(snd_path))
            else:
                break
        return sounds

    def _apply_mooney_threshold(self, img: np.ndarray) -> np.ndarray:
        """Apply Mooney thresholding to image."""
        noise = np.random.rand(*img.shape) * 100
        noisy_img = img * 0.5 + noise
        threshold = np.mean(img) * 0.47
        binary_img = (noisy_img > threshold).astype(np.uint8) * 255
        return binary_img

    def play_sound(self, sound_index: int) -> None:
        """Play a sound file."""
        if not (0 <= sound_index < len(self.sounds)):
            return
        try:
            pygame.mixer.music.load(self.sounds[sound_index])
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.01)
        except Exception as e:
            print(f"Warning: Could not play sound {sound_index}: {e}")
            time.sleep(0.5)

    def generate_block_sequence(self, target_img_idx: int, target_snd_idx: int) -> dict:
        """Generate pre/disambiguation/post sequences for a block."""
        # Pre-disambiguation: 24 trials (8 target + 16 other)
        pre_sequence = [target_img_idx] * 8

        # Get 4 random other images
        other_images = [i for i in self.image_indices if i != target_img_idx]
        random.shuffle(other_images)
        other_images = other_images[:4]

        for img in other_images:
            pre_sequence.extend([img] * 4)
        random.shuffle(pre_sequence)

        # Disambiguation: 2 trials (1 image + 1 sound)
        disambig = {
            'visual': target_img_idx,
            'audio': target_snd_idx
        }

        # Post-disambiguation: 25 trials (8 target + 17 other)
        post_sequence = [target_img_idx] * 8
        post_sequence.extend(other_images * 4)
        post_sequence = post_sequence[:17]  # Keep it to 17
        random.shuffle(post_sequence)

        return {
            'pre': pre_sequence,
            'disambig': disambig,
            'post': post_sequence
        }

    def save_session(self) -> None:
        """Save session data to CSV."""
        if not self.session_data:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mooney_{self.participant_id}_{self.modality}_{timestamp}.csv"

        data_dir = Path.home() / "mooney_data"
        data_dir.mkdir(exist_ok=True)
        filepath = data_dir / filename

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.session_data[0].keys())
                writer.writeheader()
                writer.writerows(self.session_data)
            print(f"✓ Session data saved to {filepath}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def log_trial(self, block: int, trial_type: str, stimulus_idx: int, response: str, reaction_time: float) -> None:
        """Log a trial."""
        record = {
            'participant_id': self.participant_id,
            'block': block,
            'trial_number': self.current_trial,
            'trial_type': trial_type,
            'timestamp': datetime.now().isoformat(),
            'modality': self.modality,
            'stimulus_index': stimulus_idx,
            'response': response,
            'reaction_time_ms': round(reaction_time * 1000, 2),
        }
        self.session_data.append(record)


class MooneyGUI:
    """GUI for block-based Mooney task."""

    def __init__(self, task: MooneyPredictionTask):
        self.task = task
        self.root = tk.Tk()
        self.root.title("Mooney Prediction Task - Block Design")
        self.root.minsize(600, 500)
        self.root.configure(bg='white')

        self.response = None
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
            frame, text="Block-Based Design\n(10 blocks × 52 trials = ~17 minutes)",
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
        """Start a task session."""
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

        def start():
            pid = entry.get().strip()
            if pid:
                self.task.participant_id = pid
                self.task.modality = modality
                self.task.session_data = []
                self.run_blocks()
            else:
                messagebox.showwarning("Error", "Please enter a participant ID")

        tk.Button(frame, text="Start", command=start, width=12, bg='gold', activebackground='orange').pack(pady=20)
        entry.bind('<Return>', lambda e: start())

    def run_blocks(self) -> None:
        """Run all 10 blocks."""
        num_blocks = 10

        # Use 10 unique target images/sounds
        target_indices = list(range(min(num_blocks, len(self.task.images))))
        random.shuffle(target_indices)

        for block_num in range(num_blocks):
            self.task.current_block = block_num + 1
            target_img = target_indices[block_num]
            target_snd = (block_num % len(self.task.sounds))

            self.show_block_intro(block_num + 1, num_blocks)

            block_sequence = self.task.generate_block_sequence(target_img, target_snd)

            # Pre-disambiguation phase
            for img_idx in block_sequence['pre']:
                self.task.current_trial += 1
                if self.task.modality == 'visual':
                    response, rt = self.run_visual_trial(img_idx)
                else:
                    response, rt = self.run_audio_trial(img_idx)

                if response is None:
                    break
                self.task.log_trial(block_num + 1, 'pre', img_idx, response, rt)

            # Disambiguation phase
            if response is not None:
                # Visual disambiguation
                self.task.current_trial += 1
                response, rt = self.run_visual_trial(target_img)
                if response is not None:
                    self.task.log_trial(block_num + 1, 'disambig', target_img, response, rt)

                # Audio disambiguation
                self.task.current_trial += 1
                response, rt = self.run_audio_trial(target_snd)
                if response is not None:
                    self.task.log_trial(block_num + 1, 'disambig', target_snd, response, rt)

            # Post-disambiguation phase
            if response is not None:
                for img_idx in block_sequence['post']:
                    self.task.current_trial += 1
                    if self.task.modality == 'visual':
                        response, rt = self.run_visual_trial(img_idx)
                    else:
                        response, rt = self.run_audio_trial(img_idx)

                    if response is None:
                        break
                    self.task.log_trial(block_num + 1, 'post', img_idx, response, rt)

            if response is None:
                break

        self.show_completion()

    def show_block_intro(self, block_num: int, total_blocks: int) -> None:
        """Show block introduction screen."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(
            frame, text=f"Block {block_num} of {total_blocks}",
            font=("Helvetica", 18, "bold"), bg='white', fg='blue'
        ).pack(pady=40)

        tk.Label(
            frame, text="52 trials\n(24 pre + 2 disambig + 25 post)",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=20)

        tk.Label(
            frame, text="Press SPACE to begin",
            font=("Helvetica", 11), bg='white', fg='gray'
        ).pack(pady=20)

        self.response = None
        def on_space(event):
            self.response = 'continue'

        self.root.bind('<space>', on_space)
        while self.response is None:
            self.root.update()
            time.sleep(0.01)
        self.root.unbind('<space>')

    def run_visual_trial(self, img_idx: int) -> Tuple[Optional[str], float]:
        """Run a visual trial."""
        self.clear()

        img = self.task.images[img_idx]
        thresholded = self.task._apply_mooney_threshold(img)

        img_pil = Image.fromarray(thresholded.astype('uint8'))
        img_pil = img_pil.resize((300, 300))

        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img_pil)

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        img_label = tk.Label(frame, image=photo, bg='white')
        img_label.image = photo
        img_label.pack(pady=20)

        tk.Label(
            frame,
            text="KNOWN (→) or UNKNOWN (←)?",
            font=("Helvetica", 10), bg='white', fg='black'
        ).pack(pady=10)

        self.response = None
        self.task.trial_start_time = time.time()

        def on_key(event):
            if event.keysym == 'Left':
                self.response = 'Unknown'
            elif event.keysym == 'Right':
                self.response = 'Known'

        self.root.bind('<Left>', on_key)
        self.root.bind('<Right>', on_key)

        while self.response is None:
            self.root.update()
            time.sleep(0.01)

        rt = time.time() - self.task.trial_start_time
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')

        return self.response, rt

    def run_audio_trial(self, snd_idx: int) -> Tuple[Optional[str], float]:
        """Run an audio trial."""
        self.clear()

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        tk.Label(
            frame, text="Playing audio...\n\nHIGHER (→) or LOWER (←)?",
            font=("Helvetica", 11), bg='white', fg='black'
        ).pack(pady=30)

        self.response = None
        self.task.trial_start_time = time.time()
        self.task.play_sound(snd_idx)

        def on_key(event):
            if event.keysym == 'Left':
                self.response = 'Lower'
            elif event.keysym == 'Right':
                self.response = 'Higher'

        self.root.bind('<Left>', on_key)
        self.root.bind('<Right>', on_key)

        while self.response is None:
            self.root.update()
            time.sleep(0.01)

        rt = time.time() - self.task.trial_start_time
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')

        return self.response, rt

    def show_completion(self) -> None:
        """Show completion screen."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text="Experiment Complete!",
                font=("Helvetica", 18, "bold"), bg='white', fg='green').pack(pady=30)

        tk.Label(
            frame,
            text=f"Participant: {self.task.participant_id}\nModality: {self.task.modality.upper()}\nTrials Completed: {len(self.task.session_data)}",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=20)

        self.task.save_session()

        tk.Label(
            frame, text="Thank you for participating!",
            font=("Helvetica", 11), bg='white', fg='gray'
        ).pack(pady=20)

        tk.Button(frame, text="Close", command=self.root.quit, width=12, bg='lightcoral', activebackground='salmon').pack(pady=20)

    def clear(self) -> None:
        """Clear all widgets."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def run(self) -> None:
        """Start GUI."""
        self.root.mainloop()


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    images_dir = script_dir / "stimuli" / "images"
    sounds_dir = script_dir / "stimuli" / "sounds"

    if not images_dir.exists() or not sounds_dir.exists():
        root = tk.Tk()
        root.withdraw()

        if not images_dir.exists():
            images_dir = Path(filedialog.askdirectory(title="Select folder containing Mooney images"))

        if not sounds_dir.exists():
            sounds_dir = Path(filedialog.askdirectory(title="Select folder containing sound files"))

        root.destroy()

    try:
        task = MooneyPredictionTask(images_dir, sounds_dir)
        gui = MooneyGUI(task)
        gui.run()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start task:\n{e}")
        raise


if __name__ == '__main__':
    main()
ENDFILEcat > ~/mooney-prediction-task/mooney_prediction_task_blocks.py << 'ENDFILE'
#!/usr/bin/env python3
"""
Mooney Prediction Task - Block-Based Implementation
====================================================

Implements the predictive brain experiment with block structure:
- Each block: 52 trials (pre-disambiguation 24 + disambiguation 2 + post-disambiguation 25)
- 10 blocks with unique target images/audios per block
- Target stimuli oversampled to test predictive coding

Requirements:
    - pillow (PIL)
    - numpy
    - pygame (for audio playback)

Install: pip install pillow numpy pygame

Usage:
    python mooney_prediction_task_blocks.py
"""

import os
import sys
import csv
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
from PIL import Image
import pygame
import tkinter as tk
from tkinter import messagebox, filedialog


class MooneyPredictionTask:
    """Block-based Mooney prediction task implementation."""

    def __init__(self, images_dir: Path, sounds_dir: Path):
        self.images_dir = Path(images_dir)
        self.sounds_dir = Path(sounds_dir)

        pygame.mixer.init()

        self.images = self._load_images()
        self.sounds = self._load_sounds()

        if len(self.images) < 10:
            raise ValueError(f"Need at least 10 images, found {len(self.images)}")
        if len(self.sounds) < 10:
            raise ValueError(f"Need at least 10 sounds, found {len(self.sounds)}")

        print(f"✓ Loaded {len(self.images)} images")
        print(f"✓ Loaded {len(self.sounds)} sounds")

        # Session tracking
        self.participant_id = None
        self.modality = None
        self.session_data = []
        self.current_trial = 0
        self.current_block = 0
        self.trial_start_time = None

        # Available stimuli (will be shuffled for each block)
        self.image_indices = list(range(len(self.images)))
        self.sound_indices = list(range(len(self.sounds)))

    def _load_images(self) -> List[np.ndarray]:
        """Load and preprocess Mooney images."""
        images = []
        for i in range(1, 20):
            img_path = self.images_dir / f"{i}.jpg"
            if img_path.exists():
                try:
                    img = Image.open(img_path)
                    img = img.convert('L')
                    img = img.resize((512, 512))
                    images.append(np.array(img))
                except Exception as e:
                    print(f"Warning: Could not load {img_path}: {e}")
            else:
                break
        return images

    def _load_sounds(self) -> List[str]:
        """Load sound file paths."""
        sounds = []
        for i in range(1, 40):
            snd_path = self.sounds_dir / f"{i}.mp3"
            if snd_path.exists():
                sounds.append(str(snd_path))
            else:
                break
        return sounds

    def _apply_mooney_threshold(self, img: np.ndarray) -> np.ndarray:
        """Apply Mooney thresholding to image."""
        noise = np.random.rand(*img.shape) * 100
        noisy_img = img * 0.5 + noise
        threshold = np.mean(img) * 0.47
        binary_img = (noisy_img > threshold).astype(np.uint8) * 255
        return binary_img

    def play_sound(self, sound_index: int) -> None:
        """Play a sound file."""
        if not (0 <= sound_index < len(self.sounds)):
            return
        try:
            pygame.mixer.music.load(self.sounds[sound_index])
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.01)
        except Exception as e:
            print(f"Warning: Could not play sound {sound_index}: {e}")
            time.sleep(0.5)

    def generate_block_sequence(self, target_img_idx: int, target_snd_idx: int) -> dict:
        """Generate pre/disambiguation/post sequences for a block."""
        # Pre-disambiguation: 24 trials (8 target + 16 other)
        pre_sequence = [target_img_idx] * 8

        # Get 4 random other images
        other_images = [i for i in self.image_indices if i != target_img_idx]
        random.shuffle(other_images)
        other_images = other_images[:4]

        for img in other_images:
            pre_sequence.extend([img] * 4)
        random.shuffle(pre_sequence)

        # Disambiguation: 2 trials (1 image + 1 sound)
        disambig = {
            'visual': target_img_idx,
            'audio': target_snd_idx
        }

        # Post-disambiguation: 25 trials (8 target + 17 other)
        post_sequence = [target_img_idx] * 8
        post_sequence.extend(other_images * 4)
        post_sequence = post_sequence[:17]  # Keep it to 17
        random.shuffle(post_sequence)

        return {
            'pre': pre_sequence,
            'disambig': disambig,
            'post': post_sequence
        }

    def save_session(self) -> None:
        """Save session data to CSV."""
        if not self.session_data:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mooney_{self.participant_id}_{self.modality}_{timestamp}.csv"

        data_dir = Path.home() / "mooney_data"
        data_dir.mkdir(exist_ok=True)
        filepath = data_dir / filename

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.session_data[0].keys())
                writer.writeheader()
                writer.writerows(self.session_data)
            print(f"✓ Session data saved to {filepath}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def log_trial(self, block: int, trial_type: str, stimulus_idx: int, response: str, reaction_time: float) -> None:
        """Log a trial."""
        record = {
            'participant_id': self.participant_id,
            'block': block,
            'trial_number': self.current_trial,
            'trial_type': trial_type,
            'timestamp': datetime.now().isoformat(),
            'modality': self.modality,
            'stimulus_index': stimulus_idx,
            'response': response,
            'reaction_time_ms': round(reaction_time * 1000, 2),
        }
        self.session_data.append(record)


class MooneyGUI:
    """GUI for block-based Mooney task."""

    def __init__(self, task: MooneyPredictionTask):
        self.task = task
        self.root = tk.Tk()
        self.root.title("Mooney Prediction Task - Block Design")
        self.root.minsize(600, 500)
        self.root.configure(bg='white')

        self.response = None
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
            frame, text="Block-Based Design\n(10 blocks × 52 trials = ~17 minutes)",
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
        """Start a task session."""
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

        def start():
            pid = entry.get().strip()
            if pid:
                self.task.participant_id = pid
                self.task.modality = modality
                self.task.session_data = []
                self.run_blocks()
            else:
                messagebox.showwarning("Error", "Please enter a participant ID")

        tk.Button(frame, text="Start", command=start, width=12, bg='gold', activebackground='orange').pack(pady=20)
        entry.bind('<Return>', lambda e: start())

    def run_blocks(self) -> None:
        """Run all 10 blocks."""
        num_blocks = 10

        # Use 10 unique target images/sounds
        target_indices = list(range(min(num_blocks, len(self.task.images))))
        random.shuffle(target_indices)

        for block_num in range(num_blocks):
            self.task.current_block = block_num + 1
            target_img = target_indices[block_num]
            target_snd = (block_num % len(self.task.sounds))

            self.show_block_intro(block_num + 1, num_blocks)

            block_sequence = self.task.generate_block_sequence(target_img, target_snd)

            # Pre-disambiguation phase
            for img_idx in block_sequence['pre']:
                self.task.current_trial += 1
                if self.task.modality == 'visual':
                    response, rt = self.run_visual_trial(img_idx)
                else:
                    response, rt = self.run_audio_trial(img_idx)

                if response is None:
                    break
                self.task.log_trial(block_num + 1, 'pre', img_idx, response, rt)

            # Disambiguation phase
            if response is not None:
                # Visual disambiguation
                self.task.current_trial += 1
                response, rt = self.run_visual_trial(target_img)
                if response is not None:
                    self.task.log_trial(block_num + 1, 'disambig', target_img, response, rt)

                # Audio disambiguation
                self.task.current_trial += 1
                response, rt = self.run_audio_trial(target_snd)
                if response is not None:
                    self.task.log_trial(block_num + 1, 'disambig', target_snd, response, rt)

            # Post-disambiguation phase
            if response is not None:
                for img_idx in block_sequence['post']:
                    self.task.current_trial += 1
                    if self.task.modality == 'visual':
                        response, rt = self.run_visual_trial(img_idx)
                    else:
                        response, rt = self.run_audio_trial(img_idx)

                    if response is None:
                        break
                    self.task.log_trial(block_num + 1, 'post', img_idx, response, rt)

            if response is None:
                break

        self.show_completion()

    def show_block_intro(self, block_num: int, total_blocks: int) -> None:
        """Show block introduction screen."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(
            frame, text=f"Block {block_num} of {total_blocks}",
            font=("Helvetica", 18, "bold"), bg='white', fg='blue'
        ).pack(pady=40)

        tk.Label(
            frame, text="52 trials\n(24 pre + 2 disambig + 25 post)",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=20)

        tk.Label(
            frame, text="Press SPACE to begin",
            font=("Helvetica", 11), bg='white', fg='gray'
        ).pack(pady=20)

        self.response = None
        def on_space(event):
            self.response = 'continue'

        self.root.bind('<space>', on_space)
        while self.response is None:
            self.root.update()
            time.sleep(0.01)
        self.root.unbind('<space>')

    def run_visual_trial(self, img_idx: int) -> Tuple[Optional[str], float]:
        """Run a visual trial."""
        self.clear()

        img = self.task.images[img_idx]
        thresholded = self.task._apply_mooney_threshold(img)

        img_pil = Image.fromarray(thresholded.astype('uint8'))
        img_pil = img_pil.resize((300, 300))

        from PIL import ImageTk
        photo = ImageTk.PhotoImage(img_pil)

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        img_label = tk.Label(frame, image=photo, bg='white')
        img_label.image = photo
        img_label.pack(pady=20)

        tk.Label(
            frame,
            text="KNOWN (→) or UNKNOWN (←)?",
            font=("Helvetica", 10), bg='white', fg='black'
        ).pack(pady=10)

        self.response = None
        self.task.trial_start_time = time.time()

        def on_key(event):
            if event.keysym == 'Left':
                self.response = 'Unknown'
            elif event.keysym == 'Right':
                self.response = 'Known'

        self.root.bind('<Left>', on_key)
        self.root.bind('<Right>', on_key)

        while self.response is None:
            self.root.update()
            time.sleep(0.01)

        rt = time.time() - self.task.trial_start_time
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')

        return self.response, rt

    def run_audio_trial(self, snd_idx: int) -> Tuple[Optional[str], float]:
        """Run an audio trial."""
        self.clear()

        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text=f"Trial {self.task.current_trial}",
                font=("Helvetica", 12), bg='white', fg='black').pack(pady=10)

        tk.Label(
            frame, text="Playing audio...\n\nHIGHER (→) or LOWER (←)?",
            font=("Helvetica", 11), bg='white', fg='black'
        ).pack(pady=30)

        self.response = None
        self.task.trial_start_time = time.time()
        self.task.play_sound(snd_idx)

        def on_key(event):
            if event.keysym == 'Left':
                self.response = 'Lower'
            elif event.keysym == 'Right':
                self.response = 'Higher'

        self.root.bind('<Left>', on_key)
        self.root.bind('<Right>', on_key)

        while self.response is None:
            self.root.update()
            time.sleep(0.01)

        rt = time.time() - self.task.trial_start_time
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')

        return self.response, rt

    def show_completion(self) -> None:
        """Show completion screen."""
        self.clear()
        frame = tk.Frame(self.root, bg='white')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text="Experiment Complete!",
                font=("Helvetica", 18, "bold"), bg='white', fg='green').pack(pady=30)

        tk.Label(
            frame,
            text=f"Participant: {self.task.participant_id}\nModality: {self.task.modality.upper()}\nTrials Completed: {len(self.task.session_data)}",
            font=("Helvetica", 12), bg='white', fg='black'
        ).pack(pady=20)

        self.task.save_session()

        tk.Label(
            frame, text="Thank you for participating!",
            font=("Helvetica", 11), bg='white', fg='gray'
        ).pack(pady=20)

        tk.Button(frame, text="Close", command=self.root.quit, width=12, bg='lightcoral', activebackground='salmon').pack(pady=20)

    def clear(self) -> None:
        """Clear all widgets."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def run(self) -> None:
        """Start GUI."""
        self.root.mainloop()


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    images_dir = script_dir / "stimuli" / "images"
    sounds_dir = script_dir / "stimuli" / "sounds"

    if not images_dir.exists() or not sounds_dir.exists():
        root = tk.Tk()
        root.withdraw()

        if not images_dir.exists():
            images_dir = Path(filedialog.askdirectory(title="Select folder containing Mooney images"))

        if not sounds_dir.exists():
            sounds_dir = Path(filedialog.askdirectory(title="Select folder containing sound files"))

        root.destroy()

    try:
        task = MooneyPredictionTask(images_dir, sounds_dir)
        gui = MooneyGUI(task)
        gui.run()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start task:\n{e}")
        raise


if __name__ == '__main__':
    main()
