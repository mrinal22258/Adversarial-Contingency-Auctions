"""
Main application layout for ACA Mission Control interface.
Integrates styles, persistent left shell navigation, tabs, and callbacks.
"""

import gradio as gr
import pandas as pd

from acalib.demo.ui.styles import MISSION_CONTROL_CSS, SVG_ICONS
from acalib.demo.ui.tabs import (
    build_overview_view,
    build_simulate_view,
    build_experiments_view,
    build_results_view,
    build_method_view,
    build_export_view,
)
from acalib.demo.ui.callbacks import (
    update_map_choice,
    update_alloc_choice,
    run_sim_action,
    replay_from_start,
    scrub_action,
    step_tick,
    run_compare_action,
    run_20_seeds_action,
    export_json_action,
    export_csv_action,
    format_event_log_html,
)


def build_app():
    """Construct Mission Control Gradio interface with persistent navigation shell."""
    with gr.Blocks(title="Adversarial Contingency Auctions — Mission Control") as demo:
        demo.css = MISSION_CONTROL_CSS

        # Global Session State
        history_state = gr.State([])
        events_state = gr.State([])
        env_meta_state = gr.State({
            "map_name": "Boston Downtown",
            "adversary_name": "Reactive",
            "allocator_name": "ACA (Ours)",
            "family": "road_osmnx",
            "variant": "none",
            "n_nodes": 216,
        })
        summary_state = gr.State({})
        timer_running = gr.State(False)

        # Autoplay timer
        timer = gr.Timer(value=0.25, active=False)

        # Header Section
        with gr.Column(elem_classes=["header-container"]):
            gr.Markdown(
                """
                # Adversarial Contingency Auctions (ACA) — Mission Control
                > **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**  
                <span class="badge-tag badge-real">[Real Maps]</span>
                <span class="badge-tag badge-sim">[Discrete & Physics Sim]</span>

                <div style="margin-top: 8px; padding: 6px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; color: #475569; display: flex; flex-wrap: wrap; gap: 16px;">
                    <span><strong>Protocol:</strong> Protocol v6 registered; execution pending</span>
                    <span><strong>Displayed results:</strong> protocol v5, data hash <code>a7470feb...</code></span>
                    <span><strong>Result Model:</strong> <code>v2.0.0</code></span>
                </div>
                """
            )

        # Persistent Shell Navigation Tabs (Overview, Simulate, Experiments, Results, Method, Export)
        with gr.Tabs(elem_id="main-tabs", selected="tab-simulate") as shell_tabs:
            with gr.Tab("Overview", id="tab-overview"):
                build_overview_view()

            with gr.Tab("Simulate", id="tab-simulate"):
                sim_comps = build_simulate_view()

            with gr.Tab("Experiments", id="tab-experiments"):
                exp_comps = build_experiments_view()

            with gr.Tab("Results", id="tab-results"):
                res_comps = build_results_view()

            with gr.Tab("Method", id="tab-method"):
                build_method_view()

            with gr.Tab("Export", id="tab-export"):
                exp_file_comps = build_export_view()

        # ================= CALLBACK WIRING =================

        # 1. Map dropdown change
        sim_comps["map_dropdown"].change(
            update_map_choice,
            inputs=[sim_comps["map_dropdown"]],
            outputs=[sim_comps["coarsen_radio"], sim_comps["prov_card"]],
            scroll_to_output=False,
        )

        # 2. Allocator dropdown change
        sim_comps["alloc_dropdown"].change(
            update_alloc_choice,
            inputs=[sim_comps["alloc_dropdown"]],
            outputs=[sim_comps["ablation_note"]],
            scroll_to_output=False,
        )

        # 3. Run Simulation
        sim_comps["run_btn"].click(
            run_sim_action,
            inputs=[
                sim_comps["map_dropdown"],
                sim_comps["coarsen_radio"],
                sim_comps["work_zones_toggle"],
                sim_comps["robots_slider"],
                sim_comps["tasks_slider"],
                sim_comps["adv_dropdown"],
                sim_comps["alloc_dropdown"],
                sim_comps["max_steps_slider"],
                sim_comps["comm_regime_dropdown"],
                sim_comps["comm_range_slider"],
                sim_comps["p_drop_slider"],
                sim_comps["depth_slider"],
                sim_comps["seed_number"],
            ],
            outputs=[
                history_state,
                events_state,
                env_meta_state,
                summary_state,
                sim_comps["map_plot"],
                sim_comps["map_title_md"],
                sim_comps["run_result_banner"],
                sim_comps["result_sentence_md"],
                sim_comps["kpi_done"],
                sim_comps["kpi_rate"],
                sim_comps["kpi_conf"],
                sim_comps["kpi_msgs"],
                sim_comps["kpi_trav"],
                sim_comps["kpi_blkd"],
                sim_comps["kpi_detr"],
                sim_comps["scrubber"],
                sim_comps["event_log_box"],
                sim_comps["telemetry_table"],
                sim_comps["what_happened_box"],
                sim_comps["task_failures_table"],
                sim_comps["reproduce_result_md"],
            ],
            scroll_to_output=False,
        )

        # 4. Replay from start
        sim_comps["replay_btn"].click(
            replay_from_start,
            inputs=[history_state, env_meta_state, sim_comps["work_zones_toggle"]],
            outputs=[
                sim_comps["scrubber"],
                sim_comps["map_plot"],
                sim_comps["map_title_md"],
                sim_comps["kpi_done"],
                sim_comps["kpi_rate"],
                sim_comps["kpi_conf"],
                sim_comps["kpi_msgs"],
                sim_comps["kpi_trav"],
                sim_comps["kpi_blkd"],
                sim_comps["kpi_detr"],
            ],
            scroll_to_output=False,
        )

        # 5. Timeline scrubber
        sim_comps["scrubber"].change(
            scrub_action,
            inputs=[
                sim_comps["scrubber"],
                history_state,
                events_state,
                sim_comps["event_filter_radio"],
                env_meta_state,
                sim_comps["work_zones_toggle"],
            ],
            outputs=[
                sim_comps["map_plot"],
                sim_comps["map_title_md"],
                sim_comps["kpi_done"],
                sim_comps["kpi_rate"],
                sim_comps["kpi_conf"],
                sim_comps["kpi_msgs"],
                sim_comps["kpi_trav"],
                sim_comps["kpi_blkd"],
                sim_comps["kpi_detr"],
                sim_comps["event_log_box"],
                sim_comps["telemetry_table"],
            ],
            scroll_to_output=False,
        )

        # 6. Event filter
        sim_comps["event_filter_radio"].change(
            lambda cat, evs, scr: format_event_log_html(evs, active_tick=int(scr), filter_category=cat),
            inputs=[sim_comps["event_filter_radio"], events_state, sim_comps["scrubber"]],
            outputs=[sim_comps["event_log_box"]],
            scroll_to_output=False,
        )

        # 7. Step navigation buttons
        sim_comps["step_back_btn"].click(
            lambda cur, hist: step_tick(-1, cur, len(hist)),
            inputs=[sim_comps["scrubber"], history_state],
            outputs=[sim_comps["scrubber"]],
            scroll_to_output=False,
        )

        sim_comps["step_fwd_btn"].click(
            lambda cur, hist: step_tick(1, cur, len(hist)),
            inputs=[sim_comps["scrubber"], history_state],
            outputs=[sim_comps["scrubber"]],
            scroll_to_output=False,
        )

        # 8. Autoplay toggle
        def toggle_playback(is_running):
            new_state = not is_running
            label = "Pause" if new_state else "Auto Play"
            return new_state, gr.Timer(active=new_state), label

        sim_comps["play_pause_btn"].click(
            toggle_playback,
            inputs=[timer_running],
            outputs=[timer_running, timer, sim_comps["play_pause_btn"]],
            scroll_to_output=False,
        )

        def on_tick(cur, hist):
            if not hist:
                return cur
            nxt = int(cur) + 1
            if nxt > len(hist):
                nxt = 1
            return nxt

        timer.tick(
            on_tick,
            inputs=[sim_comps["scrubber"], history_state],
            outputs=[sim_comps["scrubber"]],
            scroll_to_output=False,
        )

        # 9. Paired comparison runners
        def trigger_compare(
            map_c, coarsen_c, r_cnt, t_cnt, adv_c, alloc_c,
            m_steps, c_reg, c_range, p_d, dep, s_num,
        ):
            c_df, fig, p_df, p_note = run_compare_action(
                map_c, coarsen_c, r_cnt, t_cnt, adv_c, alloc_c,
                m_steps, c_reg, c_range, p_d, dep, s_num,
            )
            return c_df, fig, p_df, p_note, gr.Tabs(selected="tab-experiments")

        compare_inputs = [
            sim_comps["map_dropdown"],
            sim_comps["coarsen_radio"],
            sim_comps["robots_slider"],
            sim_comps["tasks_slider"],
            sim_comps["adv_dropdown"],
            sim_comps["alloc_dropdown"],
            sim_comps["max_steps_slider"],
            sim_comps["comm_regime_dropdown"],
            sim_comps["comm_range_slider"],
            sim_comps["p_drop_slider"],
            sim_comps["depth_slider"],
            sim_comps["seed_number"],
        ]
        compare_outputs = [
            exp_comps["compare_table"],
            exp_comps["compare_chart"],
            exp_comps["paper_table"],
            exp_comps["paper_note"],
            shell_tabs,
        ]

        sim_comps["compare_btn"].click(
            trigger_compare,
            inputs=compare_inputs,
            outputs=compare_outputs,
            scroll_to_output=False,
        )

        exp_comps["tab_compare_btn"].click(
            trigger_compare,
            inputs=compare_inputs,
            outputs=compare_outputs,
            scroll_to_output=False,
        )

        # 10. 20-Seed Monte Carlo Sweep
        exp_comps["run_20_seeds_btn"].click(
            run_20_seeds_action,
            inputs=[
                sim_comps["map_dropdown"],
                sim_comps["coarsen_radio"],
                sim_comps["robots_slider"],
                sim_comps["tasks_slider"],
                sim_comps["adv_dropdown"],
                sim_comps["alloc_dropdown"],
                sim_comps["max_steps_slider"],
                sim_comps["comm_regime_dropdown"],
                sim_comps["comm_range_slider"],
                sim_comps["p_drop_slider"],
                sim_comps["seed_number"],
            ],
            outputs=[
                exp_comps["monte_carlo_table"],
                exp_comps["monte_carlo_plot"],
            ],
            scroll_to_output=False,
        )

        # 11. Export actions
        def trigger_export_json(hist, summ, meta):
            fpath = export_json_action(hist, summ, meta)
            return gr.File(value=fpath, visible=bool(fpath))

        exp_file_comps["export_json_btn"].click(
            trigger_export_json,
            inputs=[history_state, summary_state, env_meta_state],
            outputs=[exp_file_comps["export_file"]],
            scroll_to_output=False,
        )

        def trigger_export_csv(hist):
            fpath = export_csv_action(hist)
            return gr.File(value=fpath, visible=bool(fpath))

        exp_file_comps["export_csv_btn"].click(
            trigger_export_csv,
            inputs=[history_state],
            outputs=[exp_file_comps["export_file"]],
            scroll_to_output=False,
        )

    return demo


def create_app():
    """Alias for build_app."""
    return build_app()
