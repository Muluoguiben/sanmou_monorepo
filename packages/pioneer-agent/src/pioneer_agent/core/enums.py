from enum import Enum


class ActionType(str, Enum):
    CLAIM_CHAPTER_REWARD = "claim_chapter_reward"
    UPGRADE_BUILDING = "upgrade_building"
    TRANSFER_MAIN_LINEUP_TO_TEAM = "transfer_main_lineup_to_team"
    ATTACK_LAND = "attack_land"
    RECRUIT_SOLDIERS = "recruit_soldiers"
    WAIT_FOR_RESOURCE = "wait_for_resource"
    WAIT_FOR_STAMINA = "wait_for_stamina"
    INSPECT_TEAM_READINESS = "inspect_team_readiness"
    ABANDON_LAND = "abandon_land"
