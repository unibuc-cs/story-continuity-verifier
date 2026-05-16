using System;
using System.Collections.Generic;
using UnityEngine;

namespace StoryFeasibility
{
    /// <summary>
    /// Asset categories mirrored by the Python checker schema.
    /// </summary>
    public enum StoryAssetCategory
    {
        Flag,
        Unique,
        Replenishable,
        Transformable,
        Critical
    }

    [Serializable]
    public sealed class StoryParameter
    {
        // Stored as a list entry so Unity can serialize transition parameters in
        // the Inspector, then exported as a JSON object.
        public string key;
        public string value;
    }

    /// <summary>
    /// ScriptableObject definition for a resource or narrative flag.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/Asset", fileName = "StoryAsset")]
    public sealed class StoryAssetDef : ScriptableObject
    {
        public string id;
        public StoryAssetCategory category = StoryAssetCategory.Flag;
        public List<string> supportQuestIds = new List<string>();
    }

    /// <summary>
    /// ScriptableObject definition for a node in the story graph.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/State", fileName = "StoryState")]
    public sealed class StoryStateDef : ScriptableObject
    {
        public string id;
        public string kind = "mission";
        public List<string> tags = new List<string>();
    }

    /// <summary>
    /// Quest metadata used by exporter diagnostics and repair suggestions.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/Quest", fileName = "StoryQuest")]
    public sealed class StoryQuestDef : ScriptableObject
    {
        public string id;
        public string role = "side";
        public List<string> preconditions = new List<string>();
        public List<StoryAssetDef> rewards = new List<StoryAssetDef>();
    }

    /// <summary>
    /// Contract for story states that should not be reached without key assets.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/Mandatory State", fileName = "MandatoryStoryState")]
    public sealed class MandatoryStoryStateDef : ScriptableObject
    {
        public StoryStateDef state;
        public List<StoryAssetDef> required = new List<StoryAssetDef>();
        public List<StoryAssetDef> recommended = new List<StoryAssetDef>();
    }

    /// <summary>
    /// Directed story action exported as a checker transition.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/Transition", fileName = "StoryTransition")]
    public sealed class StoryTransitionDef : ScriptableObject
    {
        public string id;
        public StoryStateDef from;
        public StoryStateDef to;
        public List<string> preconditions = new List<string>();
        public List<string> effects = new List<string>();
        public string actionType = "transition";
        public List<StoryParameter> parameters = new List<StoryParameter>();
        public int cost = 1;
    }

    /// <summary>
    /// Top-level authoring asset that collects one playable chapter graph.
    /// </summary>
    [CreateAssetMenu(menuName = "Story Feasibility/Chapter", fileName = "StoryChapter")]
    public sealed class StoryChapterDef : ScriptableObject
    {
        public string chapterName = "UnityPrototypeChapter";
        public StoryStateDef initialState;
        public List<StoryAssetDef> initialAssets = new List<StoryAssetDef>();
        public List<StoryStateDef> completionStates = new List<StoryStateDef>();
        public List<StoryStateDef> states = new List<StoryStateDef>();
        public List<StoryAssetDef> assets = new List<StoryAssetDef>();
        public List<StoryQuestDef> quests = new List<StoryQuestDef>();
        public List<MandatoryStoryStateDef> mandatoryStates = new List<MandatoryStoryStateDef>();
        public List<StoryTransitionDef> transitions = new List<StoryTransitionDef>();
    }
}
