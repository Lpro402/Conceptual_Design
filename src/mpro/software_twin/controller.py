"""Main System Controller — Configuration 2 mission state machine.

The controller sets states, setpoints and permissions; the chemical twin plant
answers with the reaction-side measurements; the independent safety supervisor
can override everything. Guarded transitions raise :class:`TransitionError`;
operator-correctable conditions (enclosed space, obstructed vent, missing
water, …) keep the current state and publish a ``blocker`` message instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mpro import baseline
from mpro.chemical_twin import CartridgePlant, PlantParameters
from mpro.chemical_twin.plant import thermal_loop_command

from .cartridge import CartridgeManager, FillSession
from .ev import EVCommunicationManager, HandshakeFailed
from .event_log import ServiceLoggingManager
from .hmi import instruction_for
from .power import PowerControlManager
from .safety import IndependentSafetySupervisor
from .sensors import SimulatedHardwareAbstractionLayer
from .states import CartridgeState, FaultType, IsolationLevel, SystemState, WET_STATES
from .storage import StorageSupervisor

HVIL_WINDOW_SAMPLES = 5          # SIMULATED PLACEHOLDER verification window
H2_PCT_LEL_PER_L_MIN = 4.0       # SIMULATED PLACEHOLDER vent dilution mapping

PRE_WET_ABORTABLE = frozenset({
    SystemState.ENVIRONMENT_CHECK, SystemState.AWAIT_DEPLOY, SystemState.AWAIT_CONNECT,
    SystemState.EV_HANDSHAKE, SystemState.FILL_SESSION, SystemState.CONFIRM_ACTIVATION,
})


class TransitionError(RuntimeError):
    """Raised when a guarded transition is not allowed in the current state."""


@dataclass
class MainSystemController:
    hal: SimulatedHardwareAbstractionLayer = field(default_factory=SimulatedHardwareAbstractionLayer)
    logger: ServiceLoggingManager = field(default_factory=ServiceLoggingManager)
    cartridges: CartridgeManager = field(default_factory=CartridgeManager)
    ev: EVCommunicationManager = field(default_factory=EVCommunicationManager)
    storage: StorageSupervisor = field(default_factory=StorageSupervisor)
    plant_params: PlantParameters = field(default_factory=PlantParameters)
    state: SystemState = SystemState.SYSTEM_STANDBY
    history: list[SystemState] = field(default_factory=lambda: [SystemState.SYSTEM_STANDBY])

    def __post_init__(self) -> None:
        self.power = PowerControlManager(self.hal)
        self.safety = IndependentSafetySupervisor(self.hal, self.logger)
        self.fill = FillSession()
        self.plant: CartridgePlant | None = None
        self.requested_kw = self.power.nominal_kw
        self.blocker: str | None = None
        self.isolation_warning = False
        self.reaction_clock_s: float | None = None
        self.environment: dict[str, bool] = {}
        self.telemetry: list[dict] = []
        self.logger.log("Software twin initialised in SYSTEM_STANDBY (controller asleep)")

    # ---------------------------------------------------------------- properties
    @property
    def instruction(self) -> str:
        return self.blocker or instruction_for(self.state, self)

    @property
    def remaining_events(self) -> int:
        return self.cartridges.remaining_events

    @property
    def active_faults(self) -> list[str]:
        return [f.value for f in self.safety.latched_faults]

    @property
    def delivered_kwh(self) -> float:
        return self.plant.state.net_energy_kwh if self.plant else 0.0

    @property
    def boost_allowed(self) -> bool:
        s = self.hal.sensors
        return (s.temperature_c < baseline.value("thermal", "boost_disable_c")
                and s.ambient_c < baseline.value("thermal", "boost_disable_c")
                and self.safety.isolation is IsolationLevel.NORMAL)

    # ------------------------------------------------------- standby and storage
    def wake(self, source: str = "USER_WAKE") -> None:
        self._require(SystemState.SYSTEM_STANDBY)
        if not self.storage.accept_wake(source):
            self.logger.log(f"Wake request from undefined source {source!r} ignored", "WARNING")
            return
        self.hal.actuators.aux_domains_on = True
        if source == "USER_WAKE":
            self._go(SystemState.SELF_TEST, "User wake-up")
        else:
            self.logger.log(f"Awake for storage check ({source})")

    def run_storage_check(self, lic_drop_mv_per_day: float = 5.0) -> dict:
        """[9.1] Periodic D-BIT in storage, then back to sleep within the awake limit."""
        self._require(SystemState.SYSTEM_STANDBY)
        if not self.storage.awake:
            raise TransitionError("Storage check requires a DBIT_TIMER or SERVICE_PORT wake")
        s = self.hal.sensors
        report = {
            "lic_ok": self.storage.lic_ok(s.lic_voltage_v, s.ambient_c),
            "cartridges_ready": self.remaining_events,
            "next_interval_h": self.storage.update_interval(lic_drop_mv_per_day),
        }
        self.storage.elapse(30.0)
        self.storage.sleep()
        self.hal.actuators.aux_domains_on = False
        self.logger.log(f"Storage D-BIT {report}; returning to sleep")
        return report

    def run_self_test(self) -> None:
        self._require(SystemState.SELF_TEST)
        s = self.hal.sensors
        passed = (not self.safety.fault_latched and s.hvil_closed and not s.leak_detected
                  and self.hal.pump_available and self.hal.blower_available
                  and s.contactor_feedback_valid
                  and self.storage.lic_ok(s.lic_voltage_v, s.ambient_c))
        if not passed:
            self._trip(FaultType.SELF_TEST_FAILED)
            return
        if self.remaining_events == 0:
            self._go(SystemState.SERVICE_REQUIRED, "No DRY_READY cartridge")
            return
        self._go(SystemState.ENVIRONMENT_CHECK, "Self-test passed (temperature-compensated thresholds)")

    # ------------------------------------------------------ [4.1, 5.2] environment
    def answer_environment(self, enclosed: bool, near_wall: bool = False,
                           diffuser_on_open_side: bool = False) -> None:
        self._require(SystemState.ENVIRONMENT_CHECK)
        self.environment = {"enclosed": enclosed, "near_wall": near_wall,
                            "diffuser_on_open_side": diffuser_on_open_side}
        self._evaluate_environment()

    def recheck_vent_path(self) -> None:
        self._require(SystemState.ENVIRONMENT_CHECK)
        if not self.environment:
            raise TransitionError("Answer the environment questions first")
        self._evaluate_environment()

    def _evaluate_environment(self) -> None:
        e = self.environment
        if e["enclosed"]:
            return self._block("Enclosed space: operation is blocked. Move the vehicle to open air.")
        if e["near_wall"] and not e["diffuser_on_open_side"]:
            return self._block("Vehicle is next to a wall: place the diffuser on the open side and confirm.")
        if not self.hal.sensors.vent_path_clear:
            return self._block("Vent path obstructed: clear cargo from the vents, then re-check.")
        self._go(SystemState.AWAIT_DEPLOY, "Environment accepted")

    # ------------------------------------------------------------ [2.1] deployment
    def confirm_deployment(self, diffuser_outside_confirmed: bool) -> None:
        self._require(SystemState.AWAIT_DEPLOY)
        s = self.hal.sensors
        if not s.cable_deployed:
            return self._block("Deploy the charging cable.")
        if not s.vent_deployed:
            return self._block("Deploy the vent hose.")
        if not diffuser_outside_confirmed:
            return self._block("VENT_DEPLOYED alone is not enough: confirm the whole diffuser zone is outside the vehicle.")
        self._go(SystemState.AWAIT_CONNECT, "Cable, vent and driver confirmation received")

    # ----------------------------------------------------- [8.1] connection checks
    def verify_connection(self) -> None:
        self._require(SystemState.AWAIT_CONNECT)
        s = self.hal.sensors
        if not all(self.hal.sample_hvil(HVIL_WINDOW_SAMPLES)):
            return self._block("HVIL continuity failed over the check window: reseat the connector.")
        if not self.ev.cp_valid(s.cp_voltage_v):
            return self._block(f"CP level {s.cp_voltage_v:.1f} V out of range: check the connector.")
        level = self.safety.isolation
        if level is IsolationLevel.BLOCK:
            self.logger.log("IMD below block threshold before transfer", "CRITICAL")
            return self._block("Isolation below the block threshold: power transfer is prevented.")
        self.isolation_warning = level is IsolationLevel.WARNING
        if self.isolation_warning:
            self.logger.log("IMD warning threshold: indication only, all other conditions safe", "WARNING")
        self._go(SystemState.EV_HANDSHAKE, "HVIL window, CP levels and isolation verified")

    def handshake(self, iso15118_ok: bool = True, din70121_ok: bool = True,
                  cartridge_id: int | None = None) -> None:
        self._require(SystemState.EV_HANDSHAKE)
        if not self.safety.transfer_permitted():   # safety failures never switch protocol
            self._go(SystemState.AWAIT_CONNECT, "Safety condition lost during handshake")
            return self._block("HVIL or isolation failed: re-verify the connection.")
        try:
            protocol = self.ev.handshake(iso15118_ok, din70121_ok)
        except HandshakeFailed as exc:
            self.logger.log(str(exc), "WARNING")
            self._go(SystemState.SAFE_TO_DISCONNECT, "No compatible protocol; nothing was energised")
            return
        if protocol == "DIN 70121":
            self.logger.log("ISO 15118 communication failed: DIN 70121 fallback", "WARNING")
        try:
            cartridge = self.cartridges.select(cartridge_id)
        except ValueError as exc:
            raise TransitionError(str(exc)) from exc
        self.fill = FillSession()
        self.hal.sensors.water_measured_l = 0.0
        self._go(SystemState.FILL_SESSION, f"{protocol} session; cartridge {cartridge.cartridge_id} SELECTED")

    # --------------------------------------------------------- [1.1, 1.2] filling
    def pour_water(self, liters: float) -> None:
        self._require(SystemState.FILL_SESSION)
        self.fill.pour(liters)
        self.hal.sensors.water_measured_l = self.fill.measured_l
        if self.fill.overfilled:
            self._block(f"Overfill: {self.fill.measured_l:.1f} L exceeds "
                        f"{baseline.value('water', 'reject_above_l')} L. Drain chamber 220.")
        else:
            self.blocker = None
            self.logger.log(self.fill.progress_message())

    def restart_controller(self) -> None:
        """Controller reset mid-fill: no automatic wetting; re-measure and re-confirm."""
        self._require(SystemState.FILL_SESSION, SystemState.CONFIRM_ACTIVATION)
        self.fill.restart()
        if self.state is SystemState.CONFIRM_ACTIVATION:
            self._go(SystemState.FILL_SESSION, "Restart before admission: confirmation revoked")
        self._block("Controller restarted: re-measure the water in chamber 220.")

    def remeasure_water(self) -> None:
        self._require(SystemState.FILL_SESSION)
        self.fill.remeasure(self.hal.sensors.water_measured_l)
        self.blocker = None
        self.logger.log(f"Water re-measured: {self.fill.progress_message()}")

    def drain_chamber(self, liters: float) -> None:
        self._require(SystemState.FILL_SESSION)
        self.fill.measured_l = max(0.0, self.fill.measured_l - liters)
        self.hal.sensors.water_measured_l = self.fill.measured_l
        self.blocker = None if not self.fill.overfilled else self.blocker

    def confirm_fill(self) -> None:
        self._require(SystemState.FILL_SESSION)
        if not self.fill.measurement_valid:
            return self._block("Water measurement invalid after restart: re-measure.")
        if self.fill.overfilled:
            return self._block(f"Overfill: {self.fill.measured_l:.1f} L exceeds "
                               f"{baseline.value('water', 'reject_above_l')} L. Drain chamber 220 to 1.8 L.")
        if not self.fill.ready:
            return self._block(self.fill.progress_message())
        self._go(SystemState.CONFIRM_ACTIVATION, f"{self.fill.measured_l:.2f} L measured; valve to cartridge still closed")

    def cancel_fill(self) -> None:
        self._require(SystemState.FILL_SESSION, SystemState.CONFIRM_ACTIVATION)
        self._abort_before_wetting("Fill cancelled before wetting")

    # --------------------------------------------------------- activation & prime
    def confirm_activation(self) -> None:
        self._require(SystemState.CONFIRM_ACTIVATION)
        if not (self.fill.ready and self.safety.transfer_permitted()):
            raise TransitionError("Measured water, confirmation and every safety permission are required")
        self.fill.confirmed = True
        self.cartridges.admit_water()
        self.hal.actuators.cartridge_water_valve_open = True
        s = self.hal.sensors
        self.plant = CartridgePlant(self.plant_params.with_(ambient_c=s.ambient_c, water_l=self.fill.measured_l))
        self.reaction_clock_s = 0.0
        self._go(SystemState.WATER_ADMISSION, "Irreversible: water admitted, reaction clock started")

    def complete_admission(self) -> None:
        self._require(SystemState.WATER_ADMISSION)
        self.hal.actuators.cartridge_water_valve_open = False
        self._go(SystemState.PRIME_FLOW_CHECK, f"KOH dissolved to {self.plant.molarity:.1f} M")

    def prime(self) -> None:
        self._require(SystemState.PRIME_FLOW_CHECK)
        if not (self.hal.pump_available and self.hal.blower_available):
            raise TransitionError("Pump and blowers must be available")
        a, s = self.hal.actuators, self.hal.sensors
        a.pump_on = a.process_blower_on = a.tunnel_blower_on = a.vent_open = True
        s.electrolyte_flow_lpm = 2.2
        s.stack_voltage_v, _ = self.plant.operating_point(0.0)
        low, high = baseline.value("operating_point", "stack_voltage_envelope_v")
        if not low <= s.stack_voltage_v <= high:
            raise TransitionError(f"Open-circuit {s.stack_voltage_v:.0f} V outside {low}-{high} V")
        self.cartridges.mark_active()
        self._advance_clock(baseline.value("water", "prime_and_dissolution_max_s"))
        self._go(SystemState.PRECHARGE, "Prime, airflow, gas path and thermal readiness within 60 s")

    def start_power_transfer(self, requested_kw: float | None = None) -> None:
        self._require(SystemState.PRECHARGE)
        if not self.safety.transfer_permitted():
            raise TransitionError("Safety supervisor does not permit transfer")
        self.power.precharge()
        self.requested_kw = requested_kw or self.power.nominal_kw
        self.power.enable_transfer(self.requested_kw)
        self._go(SystemState.ACTIVE_POWER, f"{self.ev.protocol} DC transfer enabled")

    def request_power(self, kw: float) -> None:
        self._require(SystemState.ACTIVE_POWER, SystemState.DERATED)
        self.requested_kw = kw
        self.logger.log(f"Operator request {kw:.1f} kW (Boost {'allowed' if self.boost_allowed else 'disabled'})")

    # ----------------------------------------------------------- continuous run
    def tick(self, seconds: float, dt_s: float = 5.0) -> None:
        """Advance simulated time in ACTIVE_POWER / DERATED using the chemical twin."""
        self._require(SystemState.ACTIVE_POWER, SystemState.DERATED)
        th = baseline.load()["thermal"]
        elapsed = 0.0
        while elapsed < seconds and self.state in {SystemState.ACTIVE_POWER, SystemState.DERATED}:
            s = self.hal.sensors
            derate = 1.0
            if s.temperature_c >= th["derate_c"]:
                derate = max(0.4, 1.0 - (s.temperature_c - th["derate_c"]) / (th["shutdown_c"] - th["derate_c"]))
            reference = self.power.limit(self.requested_kw, self.boost_allowed, derate)
            airflow = thermal_loop_command(s.temperature_c, reference) if self.hal.blower_available else 0.05
            p = self.plant.step(dt_s, reference, airflow)
            self._advance_clock(dt_s)
            s.stack_voltage_v, s.stack_current_a, s.net_power_kw = p.stack_voltage_v, p.stack_current_a, p.net_power_kw
            s.temperature_c, s.hydrogen_pct_lel = p.temperature_c, p.hydrogen_rate_l_min * H2_PCT_LEL_PER_L_MIN
            self.telemetry.append({"t_s": p.time_s, "power_kw": p.net_power_kw, "voltage_v": p.stack_voltage_v,
                                   "current_a": p.stack_current_a, "temperature_c": p.temperature_c,
                                   "energy_kwh": p.net_energy_kwh, "h2_l_min": p.hydrogen_rate_l_min,
                                   "al_kg": p.aluminum_kg})
            elapsed += dt_s

            tripped = self.safety.evaluate(reaction_running=True)
            if tripped:
                self._after_trip(tripped)
                return
            level = self.safety.isolation
            if level is IsolationLevel.WARNING and not self.isolation_warning:
                self.isolation_warning = True
                self.logger.log("IMD warning during transfer: indication, transfer continues", "WARNING")
            if self.state is SystemState.ACTIVE_POWER and s.temperature_c >= th["derate_c"]:
                self._go(SystemState.DERATED, f"Core {s.temperature_c:.1f} °C ≥ {th['derate_c']} °C")
            elif self.state is SystemState.DERATED and s.temperature_c < th["derate_c"] - 2.0:
                self._go(SystemState.ACTIVE_POWER, "Thermal margin recovered")
            target = baseline.value("operating_point", "usable_energy_per_event_kwh")
            if p.net_energy_kwh >= target or self.plant.depleted:
                self._go(SystemState.RAMP_DOWN, f"{p.net_energy_kwh:.2f} kWh delivered; controlled ramp-down")
                self.power.controlled_stop()

    def stop(self) -> None:
        """Operator STOP: controlled end after wetting, clean abort before it."""
        if self.state in {SystemState.ACTIVE_POWER, SystemState.DERATED}:
            self.power.controlled_stop()
            self._go(SystemState.RAMP_DOWN, "Operator STOP: controlled ramp-down")
        elif self.state in PRE_WET_ABORTABLE:
            self._abort_before_wetting("Operator STOP before wetting")
        else:
            raise TransitionError(f"STOP has no effect in {self.state.name}")

    def advance_shutdown(self) -> None:
        if self.state is SystemState.RAMP_DOWN:
            self.power.isolate()
            a = self.hal.actuators
            a.pump_on = False
            self.hal.sensors.electrolyte_flow_lpm = 0.0
            cartridge = self.cartridges.mark_spent(self.delivered_kwh)
            self._go(SystemState.PURGE_COOLDOWN, f"Cartridge {cartridge.cartridge_id} SPENT; purge and cooldown")
        elif self.state is SystemState.POWER_ISOLATION:
            self._go(SystemState.PURGE_COOLDOWN, "Power isolated after critical fault; purge and cooldown")
        elif self.state is SystemState.PURGE_COOLDOWN:
            a = self.hal.actuators
            a.process_blower_on = a.tunnel_blower_on = False
            if self.safety.fault_latched:
                self._go(SystemState.FAULT_LOCKED, "Wet cartridge isolated; service required")
            else:
                self._go(SystemState.SAFE_TO_DISCONNECT, "Safe voltage verified; connector released")
        else:
            raise TransitionError(f"No shutdown step in {self.state.name}")

    def disconnect(self) -> None:
        self._require(SystemState.SAFE_TO_DISCONNECT)
        self.ev.disconnect()
        self.hal.actuators.aux_domains_on = False
        self.hal.actuators.vent_open = False
        if self.remaining_events == 0:
            self._go(SystemState.SERVICE_REQUIRED, "Three cartridges used")
        else:
            self.storage.sleep()
            self._go(SystemState.SYSTEM_STANDBY, f"Stowed; {self.remaining_events} event(s) ready")

    # ------------------------------------------------------------------- faults
    def inject_fault(self, fault: FaultType) -> None:
        self._trip(fault)

    def _trip(self, fault: FaultType) -> None:
        self.safety.trip(fault)
        self._after_trip(fault)

    def _after_trip(self, fault: FaultType) -> None:
        self.power.isolate()
        if self.cartridges.wetted:
            self.cartridges.mark_faulted()
            self._go(SystemState.POWER_ISOLATION, f"{fault.value}: power isolated", "CRITICAL")
        else:
            self.cartridges.mark_faulted()        # a dry SELECTED cartridge returns to DRY_READY
            self._go(SystemState.FAULT_LOCKED, f"{fault.value} before wetting", "CRITICAL")

    def reset_demonstrator(self) -> None:
        self.hal.reset()
        self.safety.reset()
        self.ev.disconnect()
        self.cartridges = CartridgeManager()
        self.storage = StorageSupervisor()
        self.__post_init__()
        self.logger.clear()
        self.state, self.history = SystemState.SYSTEM_STANDBY, [SystemState.SYSTEM_STANDBY]
        self.logger.log("Demonstrator reset (not a real service procedure)")

    # ------------------------------------------------------------------ helpers
    def _abort_before_wetting(self, message: str) -> None:
        if self.cartridges.selected is not None:
            self.cartridges.cancel_before_wetting()
        self.fill = FillSession()
        self._go(SystemState.SAFE_TO_DISCONNECT, f"{message}; cartridge returned to DRY_READY")

    def _advance_clock(self, seconds: float) -> None:
        if self.reaction_clock_s is not None:
            self.reaction_clock_s += seconds

    def _block(self, message: str) -> None:
        self.blocker = message
        self.logger.log(f"{self.state.name} blocked: {message}", "WARNING")

    def _require(self, *allowed: SystemState) -> None:
        if self.state not in allowed:
            raise TransitionError(f"Action not allowed in {self.state.name}; expected "
                                  + ", ".join(s.name for s in allowed))

    def _go(self, state: SystemState, message: str, level: str = "INFO") -> None:
        self.state = state
        self.blocker = None
        self.history.append(state)
        self.logger.log(f"{state.name}: {message}", level)

    @property
    def wet(self) -> bool:
        return self.state in WET_STATES or self.cartridges.wetted

    def cartridge_states(self) -> list[CartridgeState]:
        return [c.state for c in self.cartridges.cartridges]
