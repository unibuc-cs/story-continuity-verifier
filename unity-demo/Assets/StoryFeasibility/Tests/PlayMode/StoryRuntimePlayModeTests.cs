using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using StoryFeasibility;
using UnityEngine;
using UnityEngine.TestTools;

namespace StoryFeasibilityTests
{
    /// <summary>
    /// Play Mode coverage for runtime execution and checker trace replay.
    /// </summary>
    public sealed class StoryRuntimePlayModeTests
    {
        private GameObject host;
        private StoryRuntime runtime;
        private StoryChapterDef chapter;

        [SetUp]
        public void SetUp()
        {
            // Build the chapter in memory so tests do not depend on generated
            // project assets or editor-only factory code.
            host = new GameObject("StoryRuntimeTestHost");
            runtime = host.AddComponent<StoryRuntime>();
            chapter = BuildChapter();
            runtime.LoadChapter(chapter);
            runtime.ResetToInitialState();
        }

        [TearDown]
        public void TearDown()
        {
            // ScriptableObject instances created with CreateInstance are not
            // scene children, so destroy them explicitly.
            Object.DestroyImmediate(host);
            Object.DestroyImmediate(chapter);
            foreach (StoryTransitionDef transition in chapter.transitions)
            {
                Object.DestroyImmediate(transition);
            }
            foreach (StoryStateDef state in chapter.states)
            {
                Object.DestroyImmediate(state);
            }
            foreach (StoryAssetDef asset in chapter.assets)
            {
                Object.DestroyImmediate(asset);
            }
        }

        [UnityTest]
        public IEnumerator ResetToInitialStateRestoresStateAndAssets()
        {
            Assert.AreEqual("Start", runtime.CurrentStateId);
            Assert.IsTrue(runtime.HasAsset("InitialFlag"));
            yield return null;
        }

        [UnityTest]
        public IEnumerator ValidTransitionAppliesEffects()
        {
            Assert.IsTrue(runtime.TryExecuteTransition("t_start_hub", out string failure), failure);
            Assert.AreEqual("Hub", runtime.CurrentStateId);
            Assert.IsTrue(runtime.HasAsset("HubUnlocked"));
            yield return null;
        }

        [UnityTest]
        public IEnumerator FailedPreconditionBlocksTransition()
        {
            Assert.IsTrue(runtime.TryExecuteTransition("t_start_hub", out string setupFailure), setupFailure);
            Assert.IsFalse(runtime.TryExecuteTransition("t_hub_boss", out string failure));
            Assert.That(failure, Does.Contain("Precondition failed"));
            Assert.AreEqual("Hub", runtime.CurrentStateId);
            yield return null;
        }

        [UnityTest]
        public IEnumerator ReplayHarnessReplaysTrace()
        {
            StoryReplayHarness harness = host.AddComponent<StoryReplayHarness>();
            typeof(StoryReplayHarness)
                .GetField("runtime", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                .SetValue(harness, runtime);

            string traceJson = "{"
                + "\"violation_id\":\"TEST_TRACE\","
                + "\"initial_state\":\"Start\","
                + "\"initial_assets\":[\"InitialFlag\"],"
                + "\"actions\":["
                + "{"
                + "\"index\":0,"
                + "\"transition_id\":\"t_start_hub\","
                + "\"action_type\":\"enter_hub\","
                + "\"from\":\"Start\","
                + "\"to\":\"Hub\","
                + "\"expected_state\":\"Hub\","
                + "\"expected_assets\":[\"InitialFlag\",\"HubUnlocked\"],"
                + "\"parameters\":[{\"key\":\"state\",\"value\":\"Hub\"}]"
                + "}"
                + "]"
                + "}";

            ReplayResult result = harness.Replay(traceJson);
            Assert.IsTrue(result.success, result.message);
            Assert.AreEqual("Hub", result.finalState);
            yield return null;
        }

        private static StoryChapterDef BuildChapter()
        {
            // The fixture contains one happy path and one blocked transition,
            // enough to test precondition handling and trace assertions.
            StoryAssetDef initialFlag = Asset("InitialFlag", StoryAssetCategory.Flag);
            StoryAssetDef hubUnlocked = Asset("HubUnlocked", StoryAssetCategory.Flag);
            StoryAssetDef bossKey = Asset("BossKey", StoryAssetCategory.Unique);

            StoryStateDef start = State("Start", "mission");
            StoryStateDef hub = State("Hub", "hub");
            StoryStateDef boss = State("Boss", "mission");

            StoryTransitionDef startHub = Transition(
                "t_start_hub",
                start,
                hub,
                new string[0],
                new[] { "AddFlag(\"HubUnlocked\")" },
                "enter_hub");

            StoryTransitionDef hubBoss = Transition(
                "t_hub_boss",
                hub,
                boss,
                new[] { "HasAsset(\"BossKey\")" },
                new string[0],
                "enter_mission");

            StoryChapterDef chapter = ScriptableObject.CreateInstance<StoryChapterDef>();
            chapter.chapterName = "RuntimeTestChapter";
            chapter.initialState = start;
            chapter.initialAssets = new List<StoryAssetDef> { initialFlag };
            chapter.completionStates = new List<StoryStateDef> { boss };
            chapter.states = new List<StoryStateDef> { start, hub, boss };
            chapter.assets = new List<StoryAssetDef> { initialFlag, hubUnlocked, bossKey };
            chapter.transitions = new List<StoryTransitionDef> { startHub, hubBoss };
            return chapter;
        }

        private static StoryStateDef State(string id, string kind)
        {
            StoryStateDef state = ScriptableObject.CreateInstance<StoryStateDef>();
            state.id = id;
            state.kind = kind;
            return state;
        }

        private static StoryAssetDef Asset(string id, StoryAssetCategory category)
        {
            StoryAssetDef asset = ScriptableObject.CreateInstance<StoryAssetDef>();
            asset.id = id;
            asset.category = category;
            return asset;
        }

        private static StoryTransitionDef Transition(
            string id,
            StoryStateDef from,
            StoryStateDef to,
            string[] preconditions,
            string[] effects,
            string actionType)
        {
            StoryTransitionDef transition = ScriptableObject.CreateInstance<StoryTransitionDef>();
            transition.id = id;
            transition.from = from;
            transition.to = to;
            transition.preconditions = new List<string>(preconditions);
            transition.effects = new List<string>(effects);
            transition.actionType = actionType;
            transition.parameters = new List<StoryParameter>
            {
                new StoryParameter { key = "target", value = to.id }
            };
            return transition;
        }
    }
}
