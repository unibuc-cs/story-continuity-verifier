using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;

namespace StoryFeasibility
{
    /// <summary>
    /// Replays checker-generated traces against StoryRuntime for Unity review.
    /// </summary>
    public sealed class StoryReplayHarness : MonoBehaviour
    {
        [SerializeField] private StoryRuntime runtime;
        [SerializeField] private TextAsset traceJson;
        [SerializeField] private bool runOnStart;
        [SerializeField] private bool writeArtifacts = true;
        [SerializeField] private bool captureScreenshot;
        [SerializeField] private string artifactDirectory = "StoryReplayArtifacts";

        public ReplayResult LastResult { get; private set; }

        private void Start()
        {
            if (runOnStart && traceJson != null)
            {
                // Auto-run is useful for attaching a trace asset to a scene and
                // collecting replay artifacts in batch mode.
                LastResult = Replay(traceJson.text);
                if (writeArtifacts)
                {
                    WriteArtifacts(LastResult);
                }
                Debug.Log(LastResult.ToSummary());
            }
        }

        /// <summary>
        /// Parses checker trace JSON and replays it against the attached runtime.
        /// </summary>
        public ReplayResult Replay(string json)
        {
            ReplayTrace trace = JsonUtility.FromJson<ReplayTrace>(json);
            return Replay(trace);
        }

        /// <summary>
        /// Replays an already parsed trace and records the first mismatch.
        /// </summary>
        public ReplayResult Replay(ReplayTrace trace)
        {
            ReplayResult result = new ReplayResult();
            result.violationId = trace.violation_id;

            if (runtime == null)
            {
                result.success = false;
                result.message = "ReplayHarness has no StoryRuntime.";
                result.logs.Add(result.message);
                return result;
            }

            runtime.ResetToInitialState();
            // The checker trace records the expected initial state/assets for
            // inspection, while the runtime source of truth is the loaded chapter.
            result.logs.Add("Reset to " + runtime.CurrentStateId);
            for (int i = 0; i < trace.actions.Count; i++)
            {
                ReplayAction action = trace.actions[i];
                result.logs.Add("Step " + i + ": " + action.transition_id + " " + action.from + " -> " + action.to);
                if (!runtime.TryExecuteTransition(action.transition_id, out string failure))
                {
                    result.success = false;
                    result.message = failure;
                    result.failedStep = i;
                    result.logs.Add(failure);
                    return result;
                }

                if (!string.IsNullOrEmpty(action.expected_state) && runtime.CurrentStateId != action.expected_state)
                {
                    result.success = false;
                    result.message = "Expected state " + action.expected_state + " but observed " + runtime.CurrentStateId;
                    result.failedStep = i;
                    result.logs.Add(result.message);
                    return result;
                }

                foreach (string expectedAsset in action.expected_assets)
                {
                    // Expected assets are a lower-bound assertion. The runtime
                    // may contain extra assets not relevant to the checker trace.
                    if (!runtime.HasAsset(expectedAsset))
                    {
                        result.success = false;
                        result.message = "Expected asset " + expectedAsset + " after " + action.transition_id;
                        result.failedStep = i;
                        result.logs.Add(result.message);
                        return result;
                    }
                }
            }

            result.success = true;
            result.message = "Replay completed.";
            result.finalState = runtime.CurrentStateId;
            result.finalAssets = new List<string>(runtime.Assets);
            result.logs.Add(result.message);
            return result;
        }

        /// <summary>
        /// Writes a JSON replay result and optionally asks Unity for a screenshot.
        /// </summary>
        public string WriteArtifacts(ReplayResult result)
        {
            string directory = Path.Combine(Application.persistentDataPath, artifactDirectory);
            Directory.CreateDirectory(directory);
            string prefix = string.IsNullOrEmpty(result.violationId) ? "replay" : result.violationId;
            string resultPath = Path.Combine(directory, prefix + "_result.json");
            result.artifactPath = resultPath;

            if (captureScreenshot)
            {
                string screenshotPath = Path.Combine(directory, prefix + "_screenshot.png");
                if (TryCaptureScreenshot(screenshotPath))
                {
                    result.screenshotPath = screenshotPath;
                }
                else
                {
                    result.logs.Add("Screenshot capture API was not available in this Unity runtime.");
                }
            }

            File.WriteAllText(resultPath, JsonUtility.ToJson(result, true));

            Debug.Log("Replay artifacts written to " + resultPath);
            return resultPath;
        }

        private static bool TryCaptureScreenshot(string screenshotPath)
        {
            // Reflection keeps the harness compatible with Unity runtimes where
            // ScreenCapture is unavailable or stripped.
            Type screenCaptureType = typeof(Application).Assembly.GetType("UnityEngine.ScreenCapture");
            MethodInfo capture = screenCaptureType != null
                ? screenCaptureType.GetMethod("CaptureScreenshot", new[] { typeof(string) })
                : null;
            if (capture == null)
            {
                return false;
            }

            capture.Invoke(null, new object[] { screenshotPath });
            return true;
        }
    }

    [Serializable]
    public sealed class ReplayTrace
    {
        // Field names match the checker JSON exactly so Unity JsonUtility can
        // deserialize traces without custom converters.
        public string violation_id;
        public string initial_state;
        public List<string> initial_assets = new List<string>();
        public List<ReplayAction> actions = new List<ReplayAction>();
    }

    [Serializable]
    public sealed class ReplayAction
    {
        public int index;
        public string transition_id;
        public string action_type;
        public string from;
        public string to;
        public string expected_state;
        public List<string> expected_assets = new List<string>();
        public List<ReplayParameter> parameters = new List<ReplayParameter>();
    }

    [Serializable]
    public sealed class ReplayParameter
    {
        public string key;
        public string value;
    }

    [Serializable]
    public sealed class ReplayResult
    {
        public bool success;
        public string violationId;
        public int failedStep = -1;
        public string message;
        public string finalState;
        public List<string> finalAssets = new List<string>();
        public List<string> logs = new List<string>();
        public string artifactPath;
        public string screenshotPath;

        public string ToSummary()
        {
            // Short status used by batch logs and manual Play Mode runs.
            if (success)
            {
                return "Replay succeeded for " + violationId + " at " + finalState;
            }

            return "Replay failed for " + violationId + " at step " + failedStep + ": " + message;
        }
    }
}
