using System.Collections.Generic;
using System.IO;
using System.Text;
using StoryFeasibility;
using UnityEditor;
using UnityEngine;

namespace StoryFeasibilityEditor
{
    /// <summary>
    /// Converts StoryChapterDef assets into the JSON contract consumed by the
    /// Python checker.
    /// </summary>
    public static class StoryGraphExporter
    {
        [MenuItem("Tools/Story Feasibility/Export Selected Story Graph")]
        public static void ExportSelectedStoryGraph()
        {
            StoryChapterDef chapter = Selection.activeObject as StoryChapterDef;
            if (chapter == null)
            {
                EditorUtility.DisplayDialog("Story Graph Export", "Select a StoryChapterDef asset first.", "OK");
                return;
            }

            string path = EditorUtility.SaveFilePanel(
                "Export Story Graph",
                Application.dataPath,
                chapter.chapterName + ".story_graph",
                "json");

            if (string.IsNullOrEmpty(path))
            {
                return;
            }

            File.WriteAllText(path, ToJson(chapter), Encoding.UTF8);
            AssetDatabase.Refresh();
            Debug.Log("Exported story graph to " + path);
        }

        /// <summary>
        /// Serializes a chapter to checker-compatible JSON.
        /// </summary>
        public static string ToJson(StoryChapterDef chapter)
        {
            // Manual serialization keeps the exported field names independent
            // from Unity's ScriptableObject field names.
            StringBuilder builder = new StringBuilder();
            builder.Append("{\n");
            AppendProperty(builder, 1, "name", chapter.chapterName, true);
            AppendStates(builder, chapter.states);
            AppendAssets(builder, chapter.assets);
            AppendQuests(builder, chapter.quests);
            AppendMandatoryStates(builder, chapter.mandatoryStates);
            AppendTransitions(builder, chapter.transitions);
            AppendProperty(builder, 1, "initial_state", chapter.initialState != null ? chapter.initialState.id : string.Empty, true);
            AppendAssetRefs(builder, 1, "initial_assets", chapter.initialAssets, true);
            AppendStateRefs(builder, 1, "completion_states", chapter.completionStates, false);
            builder.Append("}\n");
            return builder.ToString();
        }

        private static void AppendStates(StringBuilder builder, List<StoryStateDef> states)
        {
            Indent(builder, 1).Append("\"states\": [\n");
            for (int i = 0; i < states.Count; i++)
            {
                StoryStateDef state = states[i];
                Indent(builder, 2).Append("{ ");
                AppendInlineProperty(builder, "id", state != null ? state.id : string.Empty).Append(", ");
                AppendInlineProperty(builder, "kind", state != null ? state.kind : string.Empty).Append(", ");
                builder.Append("\"tags\": ");
                AppendStringArray(builder, state != null ? state.tags : new List<string>());
                builder.Append(" }");
                builder.Append(i + 1 < states.Count ? ",\n" : "\n");
            }
            Indent(builder, 1).Append("],\n");
        }

        private static void AppendAssets(StringBuilder builder, List<StoryAssetDef> assets)
        {
            Indent(builder, 1).Append("\"assets\": [\n");
            for (int i = 0; i < assets.Count; i++)
            {
                StoryAssetDef asset = assets[i];
                Indent(builder, 2).Append("{ ");
                AppendInlineProperty(builder, "id", asset != null ? asset.id : string.Empty).Append(", ");
                AppendInlineProperty(builder, "category", asset != null ? asset.category.ToString().ToLowerInvariant() : "flag");
                if (asset != null && asset.supportQuestIds.Count > 0)
                {
                    builder.Append(", \"support_quests\": ");
                    AppendStringArray(builder, asset.supportQuestIds);
                }
                builder.Append(" }");
                builder.Append(i + 1 < assets.Count ? ",\n" : "\n");
            }
            Indent(builder, 1).Append("],\n");
        }

        private static void AppendQuests(StringBuilder builder, List<StoryQuestDef> quests)
        {
            Indent(builder, 1).Append("\"quests\": [\n");
            for (int i = 0; i < quests.Count; i++)
            {
                StoryQuestDef quest = quests[i];
                Indent(builder, 2).Append("{ ");
                AppendInlineProperty(builder, "id", quest != null ? quest.id : string.Empty).Append(", ");
                AppendInlineProperty(builder, "role", quest != null ? quest.role : "side").Append(", ");
                AppendAssetRefsInline(builder, "rewards", quest != null ? quest.rewards : new List<StoryAssetDef>()).Append(", ");
                builder.Append("\"pre\": ");
                AppendStringArray(builder, quest != null ? quest.preconditions : new List<string>());
                builder.Append(" }");
                builder.Append(i + 1 < quests.Count ? ",\n" : "\n");
            }
            Indent(builder, 1).Append("],\n");
        }

        private static void AppendMandatoryStates(StringBuilder builder, List<MandatoryStoryStateDef> mandatoryStates)
        {
            Indent(builder, 1).Append("\"mandatory_story_states\": [\n");
            for (int i = 0; i < mandatoryStates.Count; i++)
            {
                MandatoryStoryStateDef mandatory = mandatoryStates[i];
                Indent(builder, 2).Append("{ ");
                AppendInlineProperty(builder, "state", mandatory != null && mandatory.state != null ? mandatory.state.id : string.Empty).Append(", ");
                AppendAssetRefsInline(builder, "required", mandatory != null ? mandatory.required : new List<StoryAssetDef>()).Append(", ");
                AppendAssetRefsInline(builder, "recommended", mandatory != null ? mandatory.recommended : new List<StoryAssetDef>());
                builder.Append(" }");
                builder.Append(i + 1 < mandatoryStates.Count ? ",\n" : "\n");
            }
            Indent(builder, 1).Append("],\n");
        }

        private static void AppendTransitions(StringBuilder builder, List<StoryTransitionDef> transitions)
        {
            // Transitions are written across multiple lines because they are the
            // most reviewed part of the exported graph.
            Indent(builder, 1).Append("\"transitions\": [\n");
            for (int i = 0; i < transitions.Count; i++)
            {
                StoryTransitionDef transition = transitions[i];
                Indent(builder, 2).Append("{\n");
                AppendProperty(builder, 3, "id", transition != null ? transition.id : string.Empty, true);
                AppendProperty(builder, 3, "from", transition != null && transition.from != null ? transition.from.id : string.Empty, true);
                AppendProperty(builder, 3, "to", transition != null && transition.to != null ? transition.to.id : string.Empty, true);
                AppendStringArrayProperty(builder, 3, "pre", transition != null ? transition.preconditions : new List<string>(), true);
                AppendStringArrayProperty(builder, 3, "eff", transition != null ? transition.effects : new List<string>(), true);
                AppendProperty(builder, 3, "action_type", transition != null ? transition.actionType : "transition", true);
                AppendParameters(builder, transition != null ? transition.parameters : new List<StoryParameter>());
                Indent(builder, 3).Append("\"cost\": ").Append(transition != null ? transition.cost : 1).Append("\n");
                Indent(builder, 2).Append("}");
                builder.Append(i + 1 < transitions.Count ? ",\n" : "\n");
            }
            Indent(builder, 1).Append("],\n");
        }

        private static void AppendParameters(StringBuilder builder, List<StoryParameter> parameters)
        {
            // Unity stores parameters as a serializable list; the checker expects
            // a compact JSON object keyed by parameter name.
            Indent(builder, 3).Append("\"params\": {");
            for (int i = 0; i < parameters.Count; i++)
            {
                StoryParameter parameter = parameters[i];
                if (i > 0)
                {
                    builder.Append(", ");
                }
                AppendJsonString(builder, parameter != null ? parameter.key : string.Empty);
                builder.Append(": ");
                AppendJsonString(builder, parameter != null ? parameter.value : string.Empty);
            }
            builder.Append("},\n");
        }

        private static void AppendProperty(StringBuilder builder, int indent, string name, string value, bool comma)
        {
            Indent(builder, indent);
            AppendInlineProperty(builder, name, value);
            builder.Append(comma ? ",\n" : "\n");
        }

        private static void AppendStringArrayProperty(StringBuilder builder, int indent, string name, List<string> values, bool comma)
        {
            Indent(builder, indent).Append("\"").Append(name).Append("\": ");
            AppendStringArray(builder, values);
            builder.Append(comma ? ",\n" : "\n");
        }

        private static void AppendAssetRefs(StringBuilder builder, int indent, string name, List<StoryAssetDef> assets, bool comma)
        {
            Indent(builder, indent).Append("\"").Append(name).Append("\": ");
            AppendAssetRefArray(builder, assets);
            builder.Append(comma ? ",\n" : "\n");
        }

        private static void AppendStateRefs(StringBuilder builder, int indent, string name, List<StoryStateDef> states, bool comma)
        {
            Indent(builder, indent).Append("\"").Append(name).Append("\": [");
            for (int i = 0; i < states.Count; i++)
            {
                if (i > 0)
                {
                    builder.Append(", ");
                }
                AppendJsonString(builder, states[i] != null ? states[i].id : string.Empty);
            }
            builder.Append("]");
            builder.Append(comma ? ",\n" : "\n");
        }

        private static StringBuilder AppendInlineProperty(StringBuilder builder, string name, string value)
        {
            builder.Append("\"").Append(name).Append("\": ");
            AppendJsonString(builder, value);
            return builder;
        }

        private static StringBuilder AppendAssetRefsInline(StringBuilder builder, string name, List<StoryAssetDef> assets)
        {
            builder.Append("\"").Append(name).Append("\": ");
            AppendAssetRefArray(builder, assets);
            return builder;
        }

        private static void AppendAssetRefArray(StringBuilder builder, List<StoryAssetDef> assets)
        {
            builder.Append("[");
            for (int i = 0; i < assets.Count; i++)
            {
                if (i > 0)
                {
                    builder.Append(", ");
                }
                AppendJsonString(builder, assets[i] != null ? assets[i].id : string.Empty);
            }
            builder.Append("]");
        }

        private static void AppendStringArray(StringBuilder builder, List<string> values)
        {
            builder.Append("[");
            for (int i = 0; i < values.Count; i++)
            {
                if (i > 0)
                {
                    builder.Append(", ");
                }
                AppendJsonString(builder, values[i]);
            }
            builder.Append("]");
        }

        private static void AppendJsonString(StringBuilder builder, string value)
        {
            // The demo data uses simple ASCII IDs. Escaping quotes and
            // backslashes is enough for current content; a production exporter
            // should route arbitrary designer text through a JSON library.
            builder.Append('"');
            if (!string.IsNullOrEmpty(value))
            {
                for (int i = 0; i < value.Length; i++)
                {
                    char c = value[i];
                    if (c == '\\' || c == '"')
                    {
                        builder.Append('\\');
                    }
                    builder.Append(c);
                }
            }
            builder.Append('"');
        }

        private static StringBuilder Indent(StringBuilder builder, int level)
        {
            for (int i = 0; i < level; i++)
            {
                builder.Append("  ");
            }
            return builder;
        }
    }
}
