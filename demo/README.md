---
title: sikaguard
emoji: 🛡️
colorFrom: green
colorTo: yellow
sdk: gradio
app_file: app.py
pinned: false
license: mit
short_description: Explainable detection of French SMS & Mobile Money scams
---

# sikaguard — demo

Gradio demo of [sikaguard](https://github.com/asaphfelix03-beep/sikaguard).

Run locally from the repository root:

```bash
pip install -e ".[demo]"
python demo/app.py
```

To deploy as a Hugging Face Space, copy `app.py`, `render.py`, `requirements.txt`
and this `README.md` into the Space repository.

Privacy: the demo stores nothing, Gradio analytics are disabled and there is no
flagging. The model version and its "not for production" status are shown on
the page.
