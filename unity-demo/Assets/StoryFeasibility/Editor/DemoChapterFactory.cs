using System.Collections.Generic;
using System.IO;
using StoryFeasibility;
using UnityEditor;
using UnityEngine;

namespace StoryFeasibilityEditor
{
    /// <summary>
    /// Builds the seeded demo chapter used by the software artefact.
    /// </summary>
    public static class DemoChapterFactory
    {
        private const string DemoFolder = "Assets/StoryFeasibility/DemoData";

        [MenuItem("Tools/Story Feasibility/Create Demo Chapter Assets")]
        public static void CreateDemoChapterAssets()
        {
            // The generated assets are intentionally deterministic so batch
            // export and Play Mode validation can be repeated during review.
            EnsureFolder("Assets/StoryFeasibility");
            EnsureFolder(DemoFolder);

            Dictionary<string, StoryStateDef> states = new Dictionary<string, StoryStateDef>();
            AddState(states, "M1_Intro", "mission", "main");
            AddState(states, "CityHub", "hub", "hub");
            AddState(states, "Q_SideSniper", "side_quest", "side");
            AddState(states, "M2_GateSetup", "mission", "main");
            AddState(states, "M3_BankHeist", "mission", "main");
            AddState(states, "M3_Escape", "mission", "main");
            AddState(states, "M5_BlackMarket", "shop", "optional");
            AddState(states, "M6_Rooftop", "mission", "main");
            AddState(states, "M7_Boss", "mission", "mandatory", "boss");
            AddState(states, "M8_Ending", "ending", "completion");
            AddState(states, "DeadEndDock", "mission", "seeded_hard_lock");
            AddState(states, "LongRecovery_1", "mission", "seeded_soft_lock");
            AddState(states, "LongRecovery_2", "mission", "seeded_soft_lock");
            AddState(states, "LongRecovery_3", "mission", "seeded_soft_lock");
            AddState(states, "LongRecovery_4", "mission", "seeded_soft_lock");
            AddState(states, "LongRecovery_5", "mission", "seeded_soft_lock");

            Dictionary<string, StoryAssetDef> assets = new Dictionary<string, StoryAssetDef>();
            AddAsset(assets, "IntroComplete", StoryAssetCategory.Flag);
            AddAsset(assets, "StoryObjectiveFlag", StoryAssetCategory.Flag);
            AddAsset(assets, "SniperRifle", StoryAssetCategory.Unique, "Q_SideSniper");
            AddAsset(assets, "SniperQuestDone", StoryAssetCategory.Flag);
            AddAsset(assets, "SniperSold", StoryAssetCategory.Flag);
            AddAsset(assets, "GateOpened", StoryAssetCategory.Flag);
            AddAsset(assets, "HeistComplete", StoryAssetCategory.Flag);
            AddAsset(assets, "EscapeStarted", StoryAssetCategory.Flag);
            AddAsset(assets, "FinaleUnlocked", StoryAssetCategory.Flag);
            AddAsset(assets, "WantedLevelGE4", StoryAssetCategory.Flag);

            Dictionary<string, StoryQuestDef> quests = new Dictionary<string, StoryQuestDef>();
            AddQuest(quests, "Q_SideSniper", "side", new[] { "NotHasFlag(\"SniperQuestDone\")" }, assets["SniperRifle"]);
            AddQuest(quests, "Q_MainGateSetup", "main", null, assets["StoryObjectiveFlag"]);
            AddQuest(quests, "Q_MainHeist", "main", null, assets["HeistComplete"]);
            AddQuest(quests, "Q_MainEscape", "main", null, assets["EscapeStarted"]);
            AddQuest(quests, "Q_MainFinale", "main", null, assets["FinaleUnlocked"]);

            MandatoryStoryStateDef mandatoryBoss = CreateAsset<MandatoryStoryStateDef>("Mandatory_M7_Boss");
            mandatoryBoss.state = states["M7_Boss"];
            // The boss contract is the main shortcut detector target.
            mandatoryBoss.required = new List<StoryAssetDef> { assets["SniperRifle"] };
            mandatoryBoss.recommended = new List<StoryAssetDef> { assets["GateOpened"] };
            EditorUtility.SetDirty(mandatoryBoss);

            List<StoryTransitionDef> transitions = new List<StoryTransitionDef>();
            // Mainline, support quest, and seeded defect transitions are kept in
            // one list so the exported graph mirrors real chapter content.
            transitions.Add(AddTransition("t_intro_city", states["M1_Intro"], states["CityHub"], null, new[] { "AddFlag(\"IntroComplete\")" }, "enter_hub", "state", "CityHub"));
            transitions.Add(AddTransition("t_city_side_sniper", states["CityHub"], states["Q_SideSniper"], new[] { "NotHasFlag(\"SniperQuestDone\")" }, new[] { "AddAsset(\"SniperRifle\")", "AddFlag(\"SniperQuestDone\")" }, "complete_quest", "quest", "Q_SideSniper"));
            transitions.Add(AddTransition("t_side_sniper_city", states["Q_SideSniper"], states["CityHub"], null, null, "enter_hub", "state", "CityHub"));
            transitions.Add(AddTransition("t_city_gate_setup", states["CityHub"], states["M2_GateSetup"], null, new[] { "AddFlag(\"StoryObjectiveFlag\")" }, "complete_mission", "mission", "M2_GateSetup"));
            transitions.Add(AddTransition("t_gate_setup_city", states["M2_GateSetup"], states["CityHub"], null, null, "enter_hub", "state", "CityHub"));
            transitions.Add(AddTransition("t_city_heist", states["CityHub"], states["M3_BankHeist"], new[] { "HasFlag(\"StoryObjectiveFlag\")" }, new[] { "AddFlag(\"HeistComplete\")" }, "complete_mission", "mission", "M3_BankHeist"));
            transitions.Add(AddTransition("t_heist_escape", states["M3_BankHeist"], states["M3_Escape"], null, new[] { "AddFlag(\"EscapeStarted\")", "AddFlag(\"WantedLevelGE4\")" }, "complete_mission", "mission", "M3_Escape"));
            transitions.Add(AddTransition("t_escape_rooftop", states["M3_Escape"], states["M6_Rooftop"], new[] { "HasFlag(\"EscapeStarted\")" }, new[] { "AddFlag(\"GateOpened\")" }, "enter_mission", "mission", "M6_Rooftop"));
            transitions.Add(AddTransition("t_rooftop_boss", states["M6_Rooftop"], states["M7_Boss"], new[] { "HasAsset(\"SniperRifle\")" }, new[] { "AddFlag(\"FinaleUnlocked\")" }, "enter_mission", "mission", "M7_Boss"));
            transitions.Add(AddTransition("t_boss_ending", states["M7_Boss"], states["M8_Ending"], null, null, "complete_mission", "mission", "M7_Boss"));
            transitions.Add(AddTransition("t_city_black_market", states["CityHub"], states["M5_BlackMarket"], new[] { "HasAsset(\"SniperRifle\")" }, new[] { "RemoveAsset(\"SniperRifle\")", "AddFlag(\"SniperSold\")" }, "sell_asset", "asset", "SniperRifle"));
            transitions.Add(AddTransition("t_black_market_city", states["M5_BlackMarket"], states["CityHub"], null, null, "enter_hub", "state", "CityHub"));
            // Seeded findings: shortcut, hard lock, and an overlong recovery
            // chain for the checker report.
            transitions.Add(AddTransition("t_city_dev_shortcut", states["CityHub"], states["M7_Boss"], new[] { "HasFlag(\"StoryObjectiveFlag\")" }, new[] { "AddFlag(\"FinaleUnlocked\")" }, "debug_enter_mission", "mission", "M7_Boss"));
            transitions.Add(AddTransition("t_city_dead_end", states["CityHub"], states["DeadEndDock"], null, null, "enter_mission", "mission", "DeadEndDock"));
            transitions.Add(AddTransition("t_city_long_recovery_1", states["CityHub"], states["LongRecovery_1"], new[] { "HasFlag(\"StoryObjectiveFlag\")" }, null, "enter_mission", "mission", "LongRecovery_1"));
            transitions.Add(AddTransition("t_long_recovery_1_2", states["LongRecovery_1"], states["LongRecovery_2"], null, null, "complete_mission", "mission", "LongRecovery_1"));
            transitions.Add(AddTransition("t_long_recovery_2_3", states["LongRecovery_2"], states["LongRecovery_3"], null, null, "complete_mission", "mission", "LongRecovery_2"));
            transitions.Add(AddTransition("t_long_recovery_3_4", states["LongRecovery_3"], states["LongRecovery_4"], null, null, "complete_mission", "mission", "LongRecovery_3"));
            transitions.Add(AddTransition("t_long_recovery_4_5", states["LongRecovery_4"], states["LongRecovery_5"], null, null, "complete_mission", "mission", "LongRecovery_4"));
            transitions.Add(AddTransition("t_long_recovery_5_city", states["LongRecovery_5"], states["CityHub"], null, null, "enter_hub", "state", "CityHub"));

            StoryChapterDef chapter = CreateAsset<StoryChapterDef>("UnityPrototypeChapter");
            chapter.chapterName = "UnityPrototypeChapter";
            chapter.initialState = states["M1_Intro"];
            chapter.completionStates = new List<StoryStateDef> { states["M8_Ending"] };
            chapter.states = new List<StoryStateDef>(states.Values);
            chapter.assets = new List<StoryAssetDef>(assets.Values);
            chapter.quests = new List<StoryQuestDef>(quests.Values);
            chapter.mandatoryStates = new List<MandatoryStoryStateDef> { mandatoryBoss };
            chapter.transitions = transitions;
            EditorUtility.SetDirty(chapter);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Selection.activeObject = chapter;
            Debug.Log("Created demo chapter assets under " + DemoFolder);
        }

        /// <summary>
        /// Batch-mode entry point used by CI/documentation commands.
        /// </summary>
        public static void ExportDemoChapterForBatch()
        {
            CreateDemoChapterAssets();
            StoryChapterDef chapter = Selection.activeObject as StoryChapterDef;
            if (chapter == null)
            {
                throw new System.InvalidOperationException("Demo chapter asset was not selected after creation.");
            }

            string exportDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Exported"));
            Directory.CreateDirectory(exportDir);
            string exportPath = Path.Combine(exportDir, "story_graph.json");
            File.WriteAllText(exportPath, StoryGraphExporter.ToJson(chapter));
            Debug.Log("Batch-exported demo story graph to " + exportPath);
        }

        private static void AddState(Dictionary<string, StoryStateDef> states, string id, string kind, params string[] tags)
        {
            StoryStateDef state = CreateAsset<StoryStateDef>("State_" + id);
            state.id = id;
            state.kind = kind;
            state.tags = new List<string>(tags);
            EditorUtility.SetDirty(state);
            states[id] = state;
        }

        private static void AddAsset(Dictionary<string, StoryAssetDef> assets, string id, StoryAssetCategory category, params string[] supportQuestIds)
        {
            StoryAssetDef asset = CreateAsset<StoryAssetDef>("Asset_" + id);
            asset.id = id;
            asset.category = category;
            asset.supportQuestIds = new List<string>(supportQuestIds);
            EditorUtility.SetDirty(asset);
            assets[id] = asset;
        }

        private static void AddQuest(Dictionary<string, StoryQuestDef> quests, string id, string role, string[] preconditions, params StoryAssetDef[] rewards)
        {
            StoryQuestDef quest = CreateAsset<StoryQuestDef>("Quest_" + id);
            quest.id = id;
            quest.role = role;
            quest.preconditions = preconditions != null ? new List<string>(preconditions) : new List<string>();
            quest.rewards = new List<StoryAssetDef>(rewards);
            EditorUtility.SetDirty(quest);
            quests[id] = quest;
        }

        private static StoryTransitionDef AddTransition(
            string id,
            StoryStateDef from,
            StoryStateDef to,
            string[] preconditions,
            string[] effects,
            string actionType,
            string parameterKey,
            string parameterValue)
        {
            StoryTransitionDef transition = CreateAsset<StoryTransitionDef>("Transition_" + id);
            transition.id = id;
            transition.from = from;
            transition.to = to;
            transition.preconditions = preconditions != null ? new List<string>(preconditions) : new List<string>();
            transition.effects = effects != null ? new List<string>(effects) : new List<string>();
            transition.actionType = actionType;
            transition.parameters = new List<StoryParameter>
            {
                new StoryParameter { key = parameterKey, value = parameterValue }
            };
            transition.cost = 1;
            EditorUtility.SetDirty(transition);
            return transition;
        }

        private static T CreateAsset<T>(string assetName) where T : ScriptableObject
        {
            string path = DemoFolder + "/" + assetName + ".asset";
            T existing = AssetDatabase.LoadAssetAtPath<T>(path);
            if (existing != null)
            {
                // Reuse assets so repeated menu or batch runs update content
                // instead of creating duplicate project objects.
                return existing;
            }

            T asset = ScriptableObject.CreateInstance<T>();
            AssetDatabase.CreateAsset(asset, path);
            return asset;
        }

        private static void EnsureFolder(string folder)
        {
            if (AssetDatabase.IsValidFolder(folder))
            {
                return;
            }

            string parent = Path.GetDirectoryName(folder).Replace("\\", "/");
            string leaf = Path.GetFileName(folder);
            AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
