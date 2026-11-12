import sys
sys.stdout.reconfigure(encoding="utf-8")

# Let's see what happens when sherpa_onnx parses words
# In sherpa-onnx, zipvoice model has a lexicon.
# Does sherpa_onnx provide a way to lookup words or tokens?
import sherpa_onnx

print("Sherpa ONNX version:", sherpa_onnx.__version__)
