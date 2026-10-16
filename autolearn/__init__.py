"""The self-improving loop: frames saved during demos are labelled automatically (checked against the
puzzle's known position) and the corner models are retrained on them every week; a retrained model is
used only if it tests better. See autolearn/README.md."""
