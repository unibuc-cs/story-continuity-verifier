# Story Continuity Report: UnityPrototypeChapter

## Mode Summary

| Mode | Configurations | Transitions | Violations | Root Causes | Description |
| --- | ---: | ---: | ---: | ---: | --- |
| SR | 16 | 20 | 3 | 3 | Structural reachability over story states; ignores quests, assets, and DSL rules. |
| AQ | 16 | 20 | 3 | 3 | Asset-agnostic reachability with quest diagnostics; ignores asset effects and DSL rules. |
| RA | 52 | 59 | 13 | 7 | Resource-aware reachability over abstract configurations; ignores DSL rules and mandatory-state contracts. |
| SC | 52 | 59 | 20 | 11 | Symbolic continuity: resource-aware graph checks plus mandatory-state requirements and DSL rules. |

## Schema Validation

- Valid: True
- Errors: 0
- Warnings: 0

## Root Causes

| Primary | Class | State | Missing | Duplicates |
| --- | --- | --- | --- | ---: |
| V0012 | `disposable_critical_resource` | `M5_BlackMarket` | SniperRifle | 1 |
| V0018 | `dsl_invariant` | `M7_Boss` | SniperRifle | 1 |
| V0020 | `dsl_invariant` | `M8_Ending` | none | 0 |
| V0001 | `hard_lock` | `DeadEndDock` | none | 3 |
| V0005 | `hard_lock` | `M3_BankHeist` | none | 1 |
| V0007 | `hard_lock` | `M3_Escape` | none | 0 |
| V0008 | `hard_lock` | `M6_Rooftop` | none | 0 |
| V0016 | `recommended_asset_missing` | `M7_Boss` | GateOpened | 1 |
| V0014 | `shortcut` | `M7_Boss` | SniperRifle | 1 |
| V0010 | `soft_lock` | `LongRecovery_1` | none | 1 |
| V0009 | `soft_lock` | `LongRecovery_2` | none | 0 |

## SC Primary Violations

### V0001 hard_lock

- Severity: error
- State: DeadEndDock
- Rule: pattern
- Root cause: hard_lock|DeadEndDock
- Duplicate of: none
- Message: Completion is no longer reachable from this configuration.
- Missing assets: none
- Trace length: 2

### V0005 hard_lock

- Severity: error
- State: M3_BankHeist
- Rule: pattern
- Root cause: hard_lock|M3_BankHeist
- Duplicate of: none
- Message: Completion is no longer reachable from this configuration.
- Missing assets: none
- Trace length: 8

### V0007 hard_lock

- Severity: error
- State: M3_Escape
- Rule: pattern
- Root cause: hard_lock|M3_Escape
- Duplicate of: none
- Message: Completion is no longer reachable from this configuration.
- Missing assets: none
- Trace length: 9

### V0008 hard_lock

- Severity: error
- State: M6_Rooftop
- Rule: pattern
- Root cause: hard_lock|M6_Rooftop
- Duplicate of: none
- Message: Completion is no longer reachable from this configuration.
- Missing assets: none
- Trace length: 10

### V0009 soft_lock

- Severity: warning
- State: LongRecovery_2
- Rule: pattern
- Root cause: soft_lock|LongRecovery_2
- Duplicate of: none
- Message: Shortest recovery path to completion is 6 transitions, above theta=5.
- Missing assets: none
- Trace length: 7

### V0010 soft_lock

- Severity: warning
- State: LongRecovery_1
- Rule: pattern
- Root cause: soft_lock|LongRecovery_1
- Duplicate of: none
- Message: Shortest recovery path to completion is 7 transitions, above theta=5.
- Missing assets: none
- Trace length: 6

### V0012 disposable_critical_resource

- Severity: error
- State: M5_BlackMarket
- Rule: pattern
- Root cause: critical_loss|SniperRifle|t_city_black_market
- Duplicate of: none
- Message: Transition 't_city_black_market' irreversibly removes critical asset 'SniperRifle' while a mandatory state still requires it.
- Missing assets: SniperRifle
- Trace length: 4

### V0014 shortcut

- Severity: error
- State: M7_Boss
- Rule: pattern
- Root cause: shortcut|M7_Boss|SniperRifle
- Duplicate of: none
- Message: Mandatory state 'M7_Boss' is reachable without required assets: SniperRifle.
- Missing assets: SniperRifle
- Trace length: 8

### V0016 recommended_asset_missing

- Severity: info
- State: M7_Boss
- Rule: pattern
- Root cause: recommended_asset_missing|M7_Boss|GateOpened
- Duplicate of: none
- Message: Mandatory state 'M7_Boss' is reachable without recommended assets: GateOpened.
- Missing assets: GateOpened
- Trace length: 6

### V0018 dsl_invariant

- Severity: error
- State: M7_Boss
- Rule: BossPrereqsMet
- Root cause: dsl_invariant|BossPrereqsMet|M7_Boss|SniperRifle
- Duplicate of: none
- Message: Rule 'BossPrereqsMet' is violated at state 'M7_Boss'.
- Missing assets: SniperRifle
- Trace length: 8

### V0020 dsl_invariant

- Severity: error
- State: M8_Ending
- Rule: NoFinalWhileHighlyWanted
- Root cause: dsl_invariant|NoFinalWhileHighlyWanted|M8_Ending|
- Duplicate of: none
- Message: Rule 'NoFinalWhileHighlyWanted' is violated at state 'M8_Ending'.
- Missing assets: none
- Trace length: 10
