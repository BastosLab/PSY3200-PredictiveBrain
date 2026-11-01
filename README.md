# Mooney Prediction Task - Block-Based Experiment

A complete implementation of the Mooney face/sound disambiguation experiment for testing predictive coding in the Predictive Brain lab course (PSY-3892, Vanderbilt University).

## Overview

This experiment measures how prior exposure to ambiguous visual and auditory stimuli affects prediction and recognition, implementing key predictions from predictive coding theory.

**Experiment Design:**
- 10 blocks with 52 trials per block (~17 minutes total)
- Each block structure:
  - Pre-disambiguation: 24 visual/audio trials (8 target + 16 non-target)
  - Disambiguation: 2 trials (visual + audio reveal target identity)
  - Post-disambiguation: 25 visual/audio trials (8 target + 17 non-target)
- Two modalities: Visual (Mooney faces) and Audio (tone discrimination)
- Data logged to CSV with trial-by-trial responses and reaction times

## Quick Start

### 1. Install Dependencies
```bash
pip install pillow numpy pygame
```

### 2. Run the Experiment
```bash
python mooney_prediction_task_blocks.py
```

### 3. Using the Interface
- Select modality (VISUAL or AUDIO)
- Enter participant ID
- Complete all 10 blocks following on-screen prompts
- Data saves automatically to `~/mooney_data/`

## Repository Contents

- `mooney_prediction_task_blocks.py` - Main experiment code (complete with GUI)
- `stimuli/images/` - 16 Mooney face images (pre-thresholded)
- `stimuli/sounds/` - 16 audio files for tone discrimination trials
- `.gitignore` - Excludes data files and generated files

## Stimulus Details

**Visual Stimuli:** 16 Mooney faces (high-contrast, ambiguous faces)
- Displayed at 300×300 pixels with procedural noise and thresholding
- Participant responds: KNOWN (→ arrow) or UNKNOWN (← arrow)

**Audio Stimuli:** 16 tone files (~1 second each)
- MP3 format, played via pygame mixer
- Participant responds: HIGHER (→ arrow) or LOWER (← arrow)

## Output Data

Results saved to: `~/mooney_data/mooney_[participant_id]_[modality]_[timestamp].csv`

Columns:
- `participant_id` - Entered at start
- `block` - Block number (1-10)
- `trial_number` - Overall trial count
- `trial_type` - 'pre', 'disambig', or 'post'
- `timestamp` - ISO format timestamp
- `modality` - 'visual' or 'audio'
- `stimulus_index` - Which image/sound (1-16)
- `response` - Known/Unknown (visual) or Higher/Lower (audio)
- `reaction_time_ms` - Time from stimulus onset to response

## Technical Details

**Language:** Python 3.7+
**GUI:** tkinter (built-in)
**Libraries:**
- PIL/Pillow (image processing)
- numpy (numeric operations)
- pygame (audio playback)

**Key Classes:**
- `MooneyPredictionTask` - Manages experiment state, stimulus loading, and data logging
- `MooneyGUI` - Tkinter interface with trial presentation

**Block Sequence Algorithm:**
- Random stimulus assignment per block
- 8 target presentations + 4 non-target images (4 trials each) in pre/post phases
- Randomized trial order within each phase
- Visual and audio stimuli paired in disambiguation phase

## For Prof. Bastos & Students

This is a complete, ready-to-run implementation. Clone the repository and run:
```bash
python mooney_prediction_task_blocks.py
```

All stimuli are included. Data will be saved automatically to your home directory.

---
PSY-3892 Predictive Brain | Vanderbilt University | Prof. André Bastos
