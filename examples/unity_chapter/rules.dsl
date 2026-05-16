-- P1: Boss prerequisites must be met.
RULE BossPrereqsMet:
  WHEN EnterMission("M7_Boss")
  REQUIRE HasAsset("SniperRifle")

-- P2: The main hub objective flag must become achievable quickly.
RULE HubObjectiveReachable:
  WHEN EnterHub("CityHub")
  REQUIRE HasFlag("StoryObjectiveFlag")
  WITHIN 2 STEPS

-- P3: Finale cannot complete while the abstract wanted level is high.
RULE NoFinalWhileHighlyWanted:
  WHEN CompleteMission("M8_Ending")
  REQUIRE WantedLevelBelow(4)

-- P4: The escape mission must immediately follow the heist.
RULE EscapeImmediatelyAfterHeist:
  WHEN CompleteMission("M3_BankHeist")
  REQUIRE NextStateIs("M3_Escape")
