# Importing model predictions

This format supports external predictions. Version 0.2 also trains and runs a local anatomy baseline; see [MODEL.md](MODEL.md). No weights trained on real endoscopy data are bundled.

Read `/api/studies/STUDY_ID/manifest` from the running local app. Use its exact study ID, zero-based frame positions and `source_sha256` values. Then import a JSON file through **Model suggestions → Import**.

```json
{
  "schema_version": 1,
  "study_id": "COPY_THE_ACTUAL_STUDY_ID",
  "model": {
    "name": "Name of the model actually run",
    "version": "version-or-commit",
    "run_id": "unique-run-identifier",
    "description": "Dataset split and preprocessing used"
  },
  "predictions": [
    {
      "position": 0,
      "image_sha256": "COPY_THE_ACTUAL_64_CHARACTER_SOURCE_HASH",
      "label": "model output label",
      "score": 0.72
    }
  ]
}
```

This example deliberately contains invalid identity placeholders. It is not a result and cannot be imported until populated with real identities. `weights_sha256` is optional model metadata. Scores must be finite and between 0 and 1; that bound does not establish calibration.

A run ID can be imported once per examination. Multiple runs remain distinct. Duplicate frame/label entries are rejected. Labels appear under model suggestions, not under dataset annotations or saved findings. **Use as reviewer label** copies text into the editable reviewer field; it requires a save and does not automatically bookmark or diagnose a frame.

The API verifies file/position consistency. It does not independently verify that an external model was trained correctly or that its supplied metadata is truthful.
