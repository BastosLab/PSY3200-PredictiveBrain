# PSY 3200 Predictive Brain: class data

This branch holds the class's session files. The task and the analysis are on
the [main branch](https://github.com/BastosLab/PSY3200-PredictiveBrain).
The task uploads each file here by itself, under the student's GitHub account.

- `class_data/visual/`: first class (everyone does the visual session)
- `class_data/audio/`: second class (everyone does the audio session)
- `class_data/checkins/`: one file per student, written by `setup_student.py`
- `class_data/demo/`: shortened test runs; the class analysis skips them

To analyse everyone's data, run this in the task folder:

```bash
python3 analysis/analyze_class.py --download
```

Do not change or delete anyone else's file.
