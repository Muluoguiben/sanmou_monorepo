from enum import Enum


class ActionType(str, Enum):
    CLAIM_CHAPTER_REWARD = "claim_chapter_reward"
    UPGRADE_BUILDING = "upgrade_building"
    TRANSFER_MAIN_LINEUP_TO_TEAM = "transfer_main_lineup_to_team"
    ATTACK_LAND = "attack_land"
    RECRUIT_SOLDIERS = "recruit_soldiers"
    WAIT_FOR_RESOURCE = "wait_for_resource"
    WAIT_FOR_STAMINA = "wait_for_stamina"
    ABANDON_LAND = "abandon_land"


class RuntimeStage(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    WAITING = "waiting"
    RECOVERING = "recovering"
    ERROR = "error"


class EventType(str, Enum):
    MANUAL_BOOT = "manual_boot"
    ACTION_COMPLETED = "action_completed"
    TEAM_RETURNED = "team_returned"
    BATTLE_RESULT_READY = "battle_result_ready"
    RECRUIT_FINISHED = "recruit_finished"
    RESOURCE_THRESHOLD_REACHED = "resource_threshold_reached"
    STAMINA_THRESHOLD_REACHED = "stamina_threshold_reached"
    CHAPTER_CLAIMABLE_NOW = "chapter_claimable_now"
    BUILDING_NOW_UPGRADEABLE = "building_now_upgradeable"
    FALLBACK_REPLAN = "fallback_replan"

