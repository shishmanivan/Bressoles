def resolve_boss_selection(level_number, defeated_count):
    """Determine which level-2 goal stage should be active."""
    if level_number != 2:
        return 0
    try:
        stage = int(defeated_count or 0)
    except (TypeError, ValueError):
        stage = 0
    return 0 if stage <= 0 else 1


def resolve_initial_button_goals(
    level_number,
    level_cfg,
    boss_selection,
    defeated_count,
    is_apper_boss,
    get_level2_goal,
    get_level3_goal,
    apper_goal_boost,
):
    """Build the initial E/M/H button goals for RoundPage."""
    if level_number == 2:
        e_goal = get_level2_goal(1, "e", boss_selection, False)
        m_goal = get_level2_goal(1, "m", boss_selection, False)
        if e_goal is None:
            e_goal = 50
        if m_goal is None:
            m_goal = 70
        if is_apper_boss:
            e_goal = apper_goal_boost(e_goal)
            m_goal = apper_goal_boost(m_goal)
        return {"e": e_goal, "m": m_goal, "h": None}

    if level_number == 3:
        e_goal = get_level3_goal(1, "e", defeated_count, False)
        m_goal = get_level3_goal(1, "m", defeated_count, False)
        h_goal = get_level3_goal(1, "h", defeated_count, False)
        if e_goal is None:
            e_goal = 60
        if m_goal is None:
            m_goal = 80
        if h_goal is None:
            h_goal = 100
        if is_apper_boss:
            e_goal = apper_goal_boost(e_goal)
            m_goal = apper_goal_boost(m_goal)
            h_goal = apper_goal_boost(h_goal)
        return {"e": e_goal, "m": m_goal, "h": h_goal}

    e_goal = level_cfg.get("E")
    m_goal = level_cfg.get("M")
    h_goal = level_cfg.get("H")
    if is_apper_boss:
        e_goal = apper_goal_boost(e_goal)
        m_goal = apper_goal_boost(m_goal)
        h_goal = apper_goal_boost(h_goal)
    return {"e": e_goal, "m": m_goal, "h": h_goal}


def refresh_button_goals_for_round(
    level_number,
    current_round,
    boss_selection,
    defeated_count,
    is_apper_boss,
    button_goals,
    get_level2_goal,
    get_level3_goal,
    apper_goal_boost,
):
    """Return updated button goals for the active round."""
    updated_goals = dict(button_goals)
    if level_number == 2:
        e_goal = get_level2_goal(current_round, "e", boss_selection, False)
        m_goal = get_level2_goal(current_round, "m", boss_selection, False)
        if is_apper_boss:
            e_goal = apper_goal_boost(e_goal)
            m_goal = apper_goal_boost(m_goal)
        updated_goals["e"] = e_goal
        updated_goals["m"] = m_goal
        return updated_goals

    if level_number == 3:
        e_goal = get_level3_goal(current_round, "e", defeated_count, False)
        m_goal = get_level3_goal(current_round, "m", defeated_count, False)
        h_goal = get_level3_goal(current_round, "h", defeated_count, False)
        if is_apper_boss:
            e_goal = apper_goal_boost(e_goal)
            m_goal = apper_goal_boost(m_goal)
            h_goal = apper_goal_boost(h_goal)
        if e_goal is not None:
            updated_goals["e"] = e_goal
        if m_goal is not None:
            updated_goals["m"] = m_goal
        if h_goal is not None:
            updated_goals["h"] = h_goal
    return updated_goals


def resolve_boss_reward_text(
    boss_filename,
    level_number,
    boss_index,
    defeated_count,
    bosses_required,
    get_boss_number_from_filename,
    get_boss_number_from_index,
    get_text,
):
    """Resolve the popup reward text shown for the upcoming boss."""
    is_last_boss = defeated_count == bosses_required - 1
    if is_last_boss:
        return get_text("LastBossReward", "LastBossReward")

    boss_number_for_text = None
    if boss_filename:
        boss_number_for_text = get_boss_number_from_filename(boss_filename)
    if not boss_number_for_text and boss_index is not None:
        boss_number_for_text = get_boss_number_from_index(level_number, boss_index, defeated_count)
    if boss_number_for_text:
        text_key = f"Boss{boss_number_for_text}Reward"
        return get_text(text_key, text_key)
    return None


def resolve_boss_goal(
    level_number,
    boss_index,
    boss_selection,
    defeated_count,
    is_apper_boss,
    boss_goals,
    get_level2_goal,
    get_level3_goal,
    apper_goal_boost,
):
    """Resolve the target goal when the boss icon is clicked."""
    if level_number == 2:
        e_boss_goal = get_level2_goal(None, "e", boss_selection, True)
        m_boss_goal = get_level2_goal(None, "m", boss_selection, True)
        boss_goal = e_boss_goal if e_boss_goal is not None else m_boss_goal
        boss_goal = boss_goal if boss_goal is not None else 70
        return apper_goal_boost(boss_goal) if is_apper_boss else boss_goal

    if level_number == 3:
        boss_goal = (
            get_level3_goal(None, "e", defeated_count, True)
            or get_level3_goal(None, "m", defeated_count, True)
            or 350
        )
        return apper_goal_boost(boss_goal) if is_apper_boss else boss_goal

    boss_key = (level_number, boss_index)
    if boss_key in boss_goals:
        boss_goal = boss_goals[boss_key]
        return apper_goal_boost(boss_goal) if is_apper_boss else boss_goal
    return apper_goal_boost(70) if is_apper_boss else 70
