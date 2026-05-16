using System;
using System.Collections.Generic;

namespace StoryFeasibility
{
    /// <summary>
    /// Runtime evaluator for the same predicate/effect mini-language used by
    /// the Python checker and exported JSON.
    /// </summary>
    public static class StoryPredicateEvaluator
    {
        /// <summary>
        /// Evaluates a supported predicate against the runtime state and assets.
        /// </summary>
        public static bool Evaluate(string expression, string currentState, ISet<string> assets)
        {
            StoryCall call = StoryCall.Parse(expression);
            if (call.Name == "HasAsset" || call.Name == "HasFlag")
            {
                return call.Args.Count > 0 && assets.Contains(call.Args[0]);
            }

            if (call.Name == "NotHasAsset" || call.Name == "NotHasFlag" || call.Name == "MissingAsset")
            {
                return call.Args.Count > 0 && !assets.Contains(call.Args[0]);
            }

            if (call.Name == "AtState" || call.Name == "NextStateIs")
            {
                return call.Args.Count > 0 && currentState == call.Args[0];
            }

            if (call.Name == "WantedLevelBelow")
            {
                if (call.Args.Count == 0)
                {
                    return false;
                }

                string bound = call.Args[0];
                // Numeric values are represented as boolean abstractions in the
                // demo, matching checker/story_checker/dsl.py.
                return assets.Contains("WantedLevelBelow" + bound) || !assets.Contains("WantedLevelGE" + bound);
            }

            if (call.Name == "AlwaysTrue" || call.Name == "True")
            {
                return true;
            }

            if (call.Name == "AlwaysFalse" || call.Name == "False")
            {
                return false;
            }

            throw new InvalidOperationException("Unsupported predicate: " + expression);
        }

        /// <summary>
        /// Applies a supported transition effect to the mutable asset set.
        /// </summary>
        public static void ApplyEffect(string expression, ISet<string> assets)
        {
            StoryCall call = StoryCall.Parse(expression);
            if (call.Args.Count == 0)
            {
                return;
            }

            string assetId = call.Args[0];
            if (call.Name == "AddAsset" || call.Name == "AddFlag")
            {
                assets.Add(assetId);
                return;
            }

            if (call.Name == "RemoveAsset" || call.Name == "RemoveFlag")
            {
                assets.Remove(assetId);
                return;
            }

            if (call.Name == "NoOp" || call.Name == "None")
            {
                return;
            }

            throw new InvalidOperationException("Unsupported effect: " + expression);
        }

        private sealed class StoryCall
        {
            public string Name;
            public List<string> Args = new List<string>();

            // The Unity-side parser intentionally accepts the simple call shape
            // used in the demo assets. The Python checker performs stricter
            // schema validation before exported content is reviewed.
            public static StoryCall Parse(string expression)
            {
                string text = expression.Trim();
                int open = text.IndexOf('(');
                int close = text.LastIndexOf(')');
                if (open <= 0 || close <= open)
                {
                    throw new InvalidOperationException("Expected call expression: " + expression);
                }

                StoryCall call = new StoryCall();
                call.Name = text.Substring(0, open).Trim();
                string argsText = text.Substring(open + 1, close - open - 1).Trim();
                if (argsText.Length == 0)
                {
                    return call;
                }

                string[] parts = argsText.Split(',');
                for (int i = 0; i < parts.Length; i++)
                {
                    call.Args.Add(TrimQuotes(parts[i].Trim()));
                }

                return call;
            }

            private static string TrimQuotes(string value)
            {
                if (value.Length >= 2)
                {
                    char first = value[0];
                    char last = value[value.Length - 1];
                    if ((first == '"' && last == '"') || (first == '\'' && last == '\''))
                    {
                        return value.Substring(1, value.Length - 2);
                    }
                }

                return value;
            }
        }
    }
}
