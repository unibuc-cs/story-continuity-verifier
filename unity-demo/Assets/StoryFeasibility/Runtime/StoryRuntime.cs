using System.Collections.Generic;
using UnityEngine;

namespace StoryFeasibility
{
    /// <summary>
    /// Minimal story runtime used to replay checker traces inside Unity.
    /// </summary>
    public sealed class StoryRuntime : MonoBehaviour
    {
        [SerializeField] private StoryChapterDef chapter;

        private readonly Dictionary<string, StoryTransitionDef> transitionsById = new Dictionary<string, StoryTransitionDef>();
        private readonly HashSet<string> assets = new HashSet<string>();

        public string CurrentStateId { get; private set; }
        public IReadOnlyCollection<string> Assets { get { return assets; } }
        public StoryChapterDef Chapter { get { return chapter; } }

        private void Awake()
        {
            if (chapter != null)
            {
                LoadChapter(chapter);
                ResetToInitialState();
            }
        }

        /// <summary>
        /// Loads transition lookup data for a chapter without changing state.
        /// </summary>
        public void LoadChapter(StoryChapterDef nextChapter)
        {
            chapter = nextChapter;
            transitionsById.Clear();
            if (chapter == null)
            {
                return;
            }

            foreach (StoryTransitionDef transition in chapter.transitions)
            {
                // Last writer wins to keep the runtime deterministic if a draft
                // chapter accidentally contains duplicate IDs; schema validation
                // reports duplicates before review.
                if (transition != null && !string.IsNullOrEmpty(transition.id))
                {
                    transitionsById[transition.id] = transition;
                }
            }
        }

        /// <summary>
        /// Restores the configured initial state and initial asset set.
        /// </summary>
        public void ResetToInitialState()
        {
            assets.Clear();
            if (chapter == null || chapter.initialState == null)
            {
                CurrentStateId = string.Empty;
                return;
            }

            CurrentStateId = chapter.initialState.id;
            foreach (StoryAssetDef asset in chapter.initialAssets)
            {
                if (asset != null && !string.IsNullOrEmpty(asset.id))
                {
                    assets.Add(asset.id);
                }
            }
        }

        /// <summary>
        /// Executes a transition if it starts at the current state and all
        /// exported preconditions evaluate to true.
        /// </summary>
        public bool TryExecuteTransition(string transitionId, out string failure)
        {
            failure = string.Empty;
            if (!transitionsById.TryGetValue(transitionId, out StoryTransitionDef transition))
            {
                failure = "Unknown transition: " + transitionId;
                return false;
            }

            if (transition.from == null || transition.to == null)
            {
                failure = "Transition is missing source or target: " + transitionId;
                return false;
            }

            if (transition.from.id != CurrentStateId)
            {
                failure = "Transition " + transitionId + " starts at " + transition.from.id + " but runtime is at " + CurrentStateId;
                return false;
            }

            foreach (string precondition in transition.preconditions)
            {
                // Preconditions are checked before any effect is applied, so a
                // partially executed transition cannot leak into a failed replay.
                if (!StoryPredicateEvaluator.Evaluate(precondition, CurrentStateId, assets))
                {
                    failure = "Precondition failed for " + transitionId + ": " + precondition;
                    return false;
                }
            }

            foreach (string effect in transition.effects)
            {
                StoryPredicateEvaluator.ApplyEffect(effect, assets);
            }

            CurrentStateId = transition.to.id;
            return true;
        }

        /// <summary>
        /// Returns true when the runtime currently contains the asset ID.
        /// </summary>
        public bool HasAsset(string assetId)
        {
            return assets.Contains(assetId);
        }
    }
}
