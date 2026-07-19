"use strict";

const STATE_ORDER = [
  "STANDBY", "SELF_TEST", "VEHICLE_CONNECTION", "CASSETTE_SELECTION",
  "WATER_ACTIVATION", "PRIMING", "PRE_CHARGE", "POWER_TRANSFER",
  "RAMP_DOWN", "PURGE_COOLDOWN", "READY",
];

const STATES = {
  STANDBY: {
    title: "Ready to Start",
    copy: "The system is stored, isolated, and ready for a rescue event.",
    style: "ready",
    action: "Wake Up System",
    actionCopy: "One action begins the guided readiness sequence.",
  },
  SELF_TEST: {
    title: "System Self-Test",
    copy: "Automatic safety and readiness checks run before vehicle connection.",
    style: "active",
    action: "Run Self-Test",
    actionCopy: "Checks isolation, HVIL, sensors, actuators, and stored readiness.",
  },
  VEHICLE_CONNECTION: {
    title: "Connect the Vehicle",
    copy: "Connect the simulated DC cable to the vehicle charging inlet.",
    style: "active",
    action: "Confirm Vehicle Connection",
    actionCopy: "The demonstrator validates the simulated link and handshake.",
  },
  CASSETTE_SELECTION: {
    title: "Select a Cartridge",
    copy: "The controller selects and isolates one dry, ready cartridge.",
    style: "active",
    action: "Select Ready Cartridge",
    actionCopy: "Only one cartridge can be selected or active at a time.",
  },
  WATER_ACTIVATION: {
    title: "Add Activation Water",
    copy: "Add water through the dedicated port and confirm the action.",
    style: "active",
    action: "Water Added",
    actionCopy: "Water activates the dry electrolyte in the selected cartridge.",
  },
  PRIMING: {
    title: "Prime the Reaction Loop",
    copy: "The pump and ventilation path prepare the system for generation.",
    style: "active",
    action: "Prime System",
    actionCopy: "Flow and ventilation are checked before electrical output begins.",
  },
  PRE_CHARGE: {
    title: "Prepare the Power Path",
    copy: "The system performs pre-charge and verifies every transfer guard.",
    style: "active",
    action: "Start Energy Transfer",
    actionCopy: "Transfer is enabled only when every simulated safety guard is valid.",
  },
  POWER_TRANSFER: {
    title: "Energy Transfer Active",
    copy: "Emergency energy is being delivered to the vehicle under continuous supervision.",
    style: "charging",
    action: "Complete Energy Transfer",
    actionCopy: "Stopping transfer begins a controlled electrical shutdown.",
  },
  DERATING: {
    title: "Power Automatically Reduced",
    copy: "The controller reduced output to preserve the simulated operating envelope.",
    style: "warning",
    action: "Complete Energy Transfer",
    actionCopy: "The rescue event can now be ended in a controlled sequence.",
  },
  RAMP_DOWN: {
    title: "Controlled Ramp-Down",
    copy: "The converter is disabled and the high-voltage output is isolated.",
    style: "active",
    action: "Begin Purge & Cooldown",
    actionCopy: "The next phase removes residual heat and gases before disconnection.",
  },
  PURGE_COOLDOWN: {
    title: "Purge & Cooldown",
    copy: "Ventilation remains active while the system reaches a safe end state.",
    style: "active",
    action: "Complete Rescue Event",
    actionCopy: "The cartridge becomes spent and system readiness is updated.",
  },
  READY: {
    title: "Rescue Event Complete",
    copy: "The vehicle received emergency energy and the system is ready for another event.",
    style: "ready",
    action: "Start Another Rescue",
    actionCopy: "The next available cartridge will be used for a new mission.",
  },
  SERVICE_REQUIRED: {
    title: "Service Required",
    copy: "All three rescue cartridges have been used and must be replaced by service staff.",
    style: "fault",
    action: "Reset Demonstrator",
    actionCopy: "Reset simulates a complete cartridge swap at a service center.",
  },
  EMERGENCY_SHUTDOWN: {
    title: "Emergency Shutdown",
    copy: "Power was interrupted and the independent safety chain forced safe outputs.",
    style: "fault",
    action: "Secure the System",
    actionCopy: "The fault remains latched until the demonstrator is reset.",
  },
  FAULT_LOCKED: {
    title: "Fault Locked",
    copy: "Further operation is blocked pending a simulated service inspection.",
    style: "fault",
    action: "Reset Demonstrator",
    actionCopy: "Reset is for demonstration only and is not a real service procedure.",
  },
};

const FAULTS = {
  E_STOP: { label: "Emergency stop pressed", value: "E-Stop", sensor: null },
  HVIL_OPEN: { label: "HVIL / interlock open", value: "HVIL open", sensor: ["hvil", false] },
  ISOLATION_FAULT: { label: "Electrical isolation fault", value: "Isolation fault", sensor: ["isolation", false] },
  OVERTEMPERATURE: { label: "Stack overtemperature", value: "Overtemperature", sensor: ["temperature", 75] },
  HYDROGEN_ALARM: { label: "Hydrogen concentration alarm", value: "Hydrogen alarm", sensor: ["hydrogen", 2] },
  LEAK: { label: "Electrolyte leak detected", value: "Leak detected", sensor: ["leak", true] },
  ABNORMAL_PRESSURE: { label: "Abnormal reaction pressure", value: "Abnormal pressure", sensor: ["pressure", 1.8] },
  LOSS_OF_FLOW: { label: "Loss of electrolyte flow", value: "Loss of flow", sensor: ["flow", 0] },
  PUMP_FAILURE: { label: "Electrolyte pump failure", value: "Pump failure", sensor: ["pumpAvailable", false] },
  FAN_FAILURE: { label: "Ventilation fan failure", value: "Fan failure", sensor: ["fanAvailable", false] },
  CONTACTOR_MISMATCH: { label: "Contactor feedback mismatch", value: "Contactor mismatch", sensor: ["contactorFeedback", false] },
};

const CASSETTE_UI = {
  DRY_READY: ["READY", "Dry cartridge available for activation", ""],
  SELECTED: ["SELECTED", "Isolated for the current rescue event", "is-selected"],
  ACTIVATING: ["ACTIVATING", "Water is activating the dry electrolyte", "is-selected"],
  ACTIVE: ["ACTIVE", "Supplying chemical energy to the Al-Air stack", "is-active"],
  SPENT: ["SPENT", "Sealed and awaiting service and recycling", "is-spent"],
  FAULTED: ["FAULTED", "Locked against further use", "is-faulted"],
};

const LCD_ACTIONS = {
  STANDBY: "WAKE UP",
  SELF_TEST: "RUN SELF-TEST",
  VEHICLE_CONNECTION: "CONFIRM EV",
  CASSETTE_SELECTION: "SELECT CARTRIDGE",
  WATER_ACTIVATION: "CONFIRM WATER",
  PRIMING: "START PRIMING",
  PRE_CHARGE: "START TRANSFER",
  POWER_TRANSFER: "STOP TRANSFER",
  DERATING: "STOP TRANSFER",
  RAMP_DOWN: "START PURGE",
  PURGE_COOLDOWN: "COMPLETE EVENT",
  READY: "NEW RESCUE",
  SERVICE_REQUIRED: "RESET DEMO",
  EMERGENCY_SHUTDOWN: "SECURE SYSTEM",
  FAULT_LOCKED: "RESET DEMO",
};

const ARCHITECTURE_MODULES = {
  main: {
    code: "SW-CTRL-01",
    title: "Main System Controller",
    purpose: "Coordinates the deterministic rescue mission without owning the independent safety decision.",
    responsibilities: ["Guarded mission-state transitions", "Operating-mode coordination", "Command arbitration across software managers"],
    inputs: "hmi_cmd | ev_status | reaction_status | power_status | fluid_status | service_state | safety_state",
    outputs: "mission_state | ev_cmd | reaction_cmd | power_cmd | fluid_cmd | log_event",
    safety: "The safety supervisor can override the controller and force safe outputs independently.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/controller.py",
  },
  hmi: {
    code: "SW-HMI-01",
    title: "HMI Manager",
    purpose: "Translates machine state into one clear operator instruction and persistent safety visibility.",
    responsibilities: ["Operator-state presentation", "Primary-action and E-Stop input", "LCD, alarm, prompt, and status rendering"],
    inputs: "mission_state | safety_state | measurements | service_state",
    outputs: "hmi_cmd | operator_ack | emergency_stop",
    safety: "The E-Stop request is routed directly to the safety path; the HMI cannot clear a latched fault.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/hmi.py",
  },
  safety: {
    code: "SW-SAFE-01",
    title: "Independent Safety Supervisor",
    purpose: "Evaluates critical simulated conditions and owns the highest-priority safe-state authority.",
    responsibilities: ["Fault evaluation and latching", "Derating and shutdown requests", "Emergency trip and direct output override"],
    inputs: "E-Stop | HVIL | isolation | temperature | H2 | leak | pressure | flow | contactor_feedback",
    outputs: "safety_state | gate_disable | contactor_open | water_stop | purge_hold",
    safety: "This module can bypass normal mission sequencing and directly force simulated actuators safe.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/safety.py",
  },
  ev: {
    code: "SW-EV-01",
    title: "EV Communication Manager",
    purpose: "Represents the boundary between mission control and a simulated EV connection and handshake.",
    responsibilities: ["Connection-state supervision", "Simulated pilot and handshake logic", "Vehicle limits and session status"],
    inputs: "ev_cmd | connector_state | pilot_state",
    outputs: "ev_status | handshake_valid | transfer_limits",
    safety: "No real CCS2 or PLC communication is implemented; invalid connection state blocks transfer.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/ev.py",
  },
  power: {
    code: "SW-PWR-01",
    title: "Power Control Manager",
    purpose: "Sequences the simulated isolated DC power path from pre-charge through controlled shutdown.",
    responsibilities: ["Pre-charge sequencing", "Converter and DC-link supervision", "Input/output contactor requests"],
    inputs: "power_cmd | safety_state | voltage | current | contactor_feedback",
    outputs: "power_status | converter_enable | contactor_commands | gate_disable_status",
    safety: "Safety trip disables the converter and opens both simulated contactors before mission logic continues.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/power.py",
  },
  reaction: {
    code: "SW-REA-01",
    title: "Cassette & Reaction Manager",
    purpose: "Controls the conceptual three-cassette lifecycle and reaction-enablement sequence.",
    responsibilities: ["Ready-cassette identification and exclusivity", "Water activation and priming sequence", "Reaction state and spent declaration"],
    inputs: "reaction_cmd | water_confirmed | flow_status | cassette_identity",
    outputs: "reaction_status | selected_cassette | water_request | spent_state",
    safety: "Only one cassette may be selected or active; water admission stops on a critical fault.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/cassette.py",
  },
  thermal: {
    code: "SW-TFM-01",
    title: "Thermal & Fluid Manager",
    purpose: "Coordinates simulated liquid flow, ventilation, purge, and cooldown responsibilities.",
    responsibilities: ["Pump, valve, and fan commands", "Flow and temperature supervision", "Purge and cooldown sequencing"],
    inputs: "fluid_cmd | temperature | flow | pressure | H2 | pump_available | fan_available",
    outputs: "fluid_status | pump_cmd | fan_cmd | valve_cmd | purge_complete",
    safety: "Critical faults stop water admission while ventilation or purge may remain active when appropriate.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/thermal_fluid.py",
  },
  service: {
    code: "SW-SVC-01",
    title: "Service & Logging Manager",
    purpose: "Maintains the demonstrator event history, cassette usage, and service-readiness state.",
    responsibilities: ["Timestamped event logging", "Remaining rescue capacity", "Service-required and cartridge records"],
    inputs: "log_event | cassette_state | fault_state | completed_event",
    outputs: "service_state | event_history | remaining_capacity",
    safety: "A service lock cannot be cleared by ordinary mission commands; demonstrator reset is explicitly non-production behavior.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/event_log.py",
  },
  hal: {
    code: "SW-HAL-01",
    title: "Simulated Hardware Abstraction Layer",
    purpose: "Provides a stable academic boundary between software logic and simulated measurements and actuators.",
    responsibilities: ["Sensor snapshot representation", "Actuator-command representation", "Separation from any real hardware or vehicle interface"],
    inputs: "simulated plant values | software actuator commands",
    outputs: "sensor snapshot | actuator feedback | communication placeholders",
    safety: "This layer is simulation-only and contains no real GPIO, CAN, PLC, contactor, pump, or valve control.",
    source: "https://github.com/Lpro402/Conceptual_Design/blob/main/software_demo/metalyte/sensors.py",
  },
};

const ARCHITECTURE_PHASE_ORDER = ["standby", "self-test", "vehicle", "cassette", "reaction", "transfer", "shutdown", "complete"];
const ARCHITECTURE_PHASE_BY_STATE = {
  STANDBY: "standby", SELF_TEST: "self-test", VEHICLE_CONNECTION: "vehicle",
  CASSETTE_SELECTION: "cassette", WATER_ACTIVATION: "reaction", PRIMING: "reaction",
  PRE_CHARGE: "transfer", POWER_TRANSFER: "transfer", DERATING: "transfer",
  RAMP_DOWN: "shutdown", PURGE_COOLDOWN: "shutdown", EMERGENCY_SHUTDOWN: "shutdown",
  READY: "complete", SERVICE_REQUIRED: "complete", FAULT_LOCKED: "complete",
};

const runtime = {
  state: "STANDBY",
  cassettes: ["DRY_READY", "DRY_READY", "DRY_READY"],
  selectedCassette: null,
  completedEvents: 0,
  selfTestPassed: false,
  vehicleConnected: false,
  fault: null,
  energyKwh: 0,
  targetEnergyKwh: 3,
  sensors: {},
  actuators: {},
  log: [],
};

let transferTimer = null;
let selectedArchitectureModule = "main";
const byId = (id) => document.getElementById(id);
const queryAll = (selector) => [...document.querySelectorAll(selector)];

function defaultSensors() {
  return {
    voltage: 57.6, current: 0, temperature: 25, flow: 0, pressure: 1,
    hydrogen: 0, hvil: true, isolation: true, leak: false,
    pumpAvailable: true, fanAvailable: true, contactorFeedback: true,
  };
}

function defaultActuators() {
  return {
    waterValve: false, pump: false, fan: false, vent: false,
    inputContactor: false, outputContactor: false, converter: false,
    gateDisable: true,
  };
}

function resetRuntime({ preserveLog = false } = {}) {
  stopTransferTimer();
  Object.assign(runtime, {
    state: "STANDBY",
    cassettes: ["DRY_READY", "DRY_READY", "DRY_READY"],
    selectedCassette: null,
    completedEvents: 0,
    selfTestPassed: false,
    vehicleConnected: false,
    fault: null,
    energyKwh: 0,
    sensors: defaultSensors(),
    actuators: defaultActuators(),
  });
  if (!preserveLog) runtime.log = [];
  addLog("Demonstrator reset to STANDBY");
  render();
}

function addLog(message, level = "INFO") {
  runtime.log.unshift({
    time: new Date().toLocaleTimeString("en-GB", { hour12: false }),
    level,
    message,
  });
  runtime.log = runtime.log.slice(0, 40);
}

function toast(message, critical = false) {
  const item = document.createElement("div");
  item.className = `toast${critical ? " is-critical" : ""}`;
  item.textContent = message;
  byId("toast-region").append(item);
  window.setTimeout(() => item.remove(), 2800);
}

function setState(state, message) {
  runtime.state = state;
  if (message) {
    const critical = state.includes("FAULT") || state.includes("EMERGENCY");
    addLog(`${state}: ${message}`, critical ? "CRITICAL" : "INFO");
  }
  if (!["POWER_TRANSFER", "DERATING"].includes(state)) stopTransferTimer();
  render();
}

function selectReadyCassette() {
  const index = runtime.cassettes.findIndex((state) => state === "DRY_READY");
  if (index < 0) return false;
  runtime.selectedCassette = index;
  runtime.cassettes[index] = "SELECTED";
  return true;
}

function handlePrimaryAction() {
  if (["SERVICE_REQUIRED", "FAULT_LOCKED"].includes(runtime.state)) {
    resetRuntime();
    toast("Demonstrator reset");
    return;
  }

  switch (runtime.state) {
    case "STANDBY":
    case "READY":
      runtime.selfTestPassed = false;
      runtime.vehicleConnected = false;
      runtime.energyKwh = 0;
      runtime.sensors = defaultSensors();
      runtime.actuators = defaultActuators();
      setState("SELF_TEST", "System wake-up completed");
      break;
    case "SELF_TEST":
      runtime.selfTestPassed = true;
      setState("VEHICLE_CONNECTION", "Self-test passed");
      toast("System self-test completed");
      break;
    case "VEHICLE_CONNECTION":
      runtime.vehicleConnected = true;
      setState("CASSETTE_SELECTION", "Vehicle link and simulated handshake confirmed");
      break;
    case "CASSETTE_SELECTION":
      if (!selectReadyCassette()) {
        setState("SERVICE_REQUIRED", "No ready cartridge available");
        break;
      }
      setState("WATER_ACTIVATION", `Cartridge ${runtime.selectedCassette + 1} selected`);
      break;
    case "WATER_ACTIVATION":
      runtime.cassettes[runtime.selectedCassette] = "ACTIVATING";
      runtime.actuators.waterValve = true;
      setState("PRIMING", "Water addition confirmed");
      break;
    case "PRIMING":
      runtime.actuators.pump = true;
      runtime.actuators.fan = true;
      runtime.actuators.vent = true;
      runtime.sensors.flow = 2.2;
      runtime.cassettes[runtime.selectedCassette] = "ACTIVE";
      setState("PRE_CHARGE", "Reaction flow and ventilation verified");
      break;
    case "PRE_CHARGE":
      if (!transferGuardsSafe()) {
        injectFault("ISOLATION_FAULT");
        break;
      }
      Object.assign(runtime.actuators, {
        inputContactor: true,
        outputContactor: true,
        converter: true,
        gateDisable: false,
      });
      runtime.sensors.current = 52;
      setState("POWER_TRANSFER", "Energy transfer enabled");
      startTransferTimer();
      break;
    case "POWER_TRANSFER":
    case "DERATING":
      runtime.sensors.current = 0;
      runtime.actuators.converter = false;
      runtime.actuators.outputContactor = false;
      runtime.actuators.gateDisable = true;
      setState("RAMP_DOWN", "Energy transfer stopped in a controlled sequence");
      break;
    case "RAMP_DOWN":
      runtime.actuators.inputContactor = false;
      runtime.actuators.waterValve = false;
      runtime.actuators.pump = false;
      runtime.sensors.flow = 0;
      setState("PURGE_COOLDOWN", "Purge and cooldown enabled");
      break;
    case "PURGE_COOLDOWN":
      runtime.actuators.fan = false;
      runtime.actuators.vent = false;
      runtime.cassettes[runtime.selectedCassette] = "SPENT";
      runtime.selectedCassette = null;
      runtime.completedEvents += 1;
      if (runtime.completedEvents >= 3) {
        setState("SERVICE_REQUIRED", "Three rescue events completed");
      } else {
        setState("READY", "Rescue event completed");
      }
      break;
    case "EMERGENCY_SHUTDOWN":
      setState("FAULT_LOCKED", "Safe state confirmed and fault latched");
      break;
    default:
      break;
  }
}

function transferGuardsSafe() {
  const s = runtime.sensors;
  return runtime.selfTestPassed && runtime.vehicleConnected
    && runtime.selectedCassette !== null && s.hvil && s.isolation && !s.leak
    && s.temperature < 65 && s.hydrogen < 1
    && s.pressure >= 0.7 && s.pressure <= 1.5 && s.flow >= 0.5
    && s.pumpAvailable && s.fanAvailable && s.contactorFeedback;
}

function injectFault(faultKey) {
  const fault = FAULTS[faultKey];
  if (!fault) return;
  runtime.fault = faultKey;
  if (fault.sensor) runtime.sensors[fault.sensor[0]] = fault.sensor[1];
  if (faultKey === "PUMP_FAILURE") {
    runtime.actuators.pump = false;
    runtime.sensors.flow = 0;
  }
  if (faultKey === "FAN_FAILURE") runtime.actuators.fan = false;
  safeOutputs();
  if (runtime.selectedCassette !== null && ["ACTIVATING", "ACTIVE"].includes(runtime.cassettes[runtime.selectedCassette])) {
    runtime.cassettes[runtime.selectedCassette] = "FAULTED";
    runtime.selectedCassette = null;
  }
  setState("EMERGENCY_SHUTDOWN", `Safety override: ${fault.value}`);
  toast(`Injected fault: ${fault.label}`, true);
}

function safeOutputs() {
  runtime.sensors.current = 0;
  runtime.sensors.flow = 0;
  Object.assign(runtime.actuators, {
    waterValve: false,
    pump: false,
    inputContactor: false,
    outputContactor: false,
    converter: false,
    gateDisable: true,
    fan: runtime.sensors.fanAvailable,
    vent: runtime.sensors.fanAvailable,
  });
}

function startTransferTimer() {
  stopTransferTimer();
  transferTimer = window.setInterval(() => {
    if (!["POWER_TRANSFER", "DERATING"].includes(runtime.state)) return;
    const power = (runtime.sensors.voltage * runtime.sensors.current) / 1000;
    runtime.energyKwh = Math.min(runtime.targetEnergyKwh, runtime.energyKwh + power / 3600);
    runtime.sensors.temperature = Math.min(62, runtime.sensors.temperature + 0.035);
    runtime.sensors.hydrogen = Math.min(0.65, runtime.sensors.hydrogen + 0.0008);
    runtime.sensors.pressure = Math.min(1.18, runtime.sensors.pressure + 0.0004);
    if (runtime.sensors.temperature >= 58 && runtime.state === "POWER_TRANSFER") {
      runtime.sensors.current = 31;
      setState("DERATING", "Temperature triggered automatic derating");
      toast("Power reduced automatically");
    }
    renderLiveValues();
  }, 1000);
}

function stopTransferTimer() {
  if (transferTimer !== null) window.clearInterval(transferTimer);
  transferTimer = null;
}

function missionProgress() {
  if (["SERVICE_REQUIRED", "FAULT_LOCKED"].includes(runtime.state)) return 100;
  if (runtime.state === "EMERGENCY_SHUTDOWN") return 78;
  if (runtime.state === "DERATING") return 72;
  const index = STATE_ORDER.indexOf(runtime.state);
  return index < 0 ? 0 : Math.round((index / (STATE_ORDER.length - 1)) * 100);
}

function remainingEvents() {
  return runtime.cassettes.filter((state) => state === "DRY_READY").length;
}

function render() {
  renderHeader();
  renderMission();
  renderLCD();
  renderArchitecture();
  renderCassettes();
  renderFlow();
  renderDiagnostics();
  renderService();
  renderLog();
}

function renderHeader() {
  const faulted = Boolean(runtime.fault);
  byId("header-status").textContent = faulted ? "Active Fault" : STATES[runtime.state].title;
  byId("header-status").parentElement.classList.toggle("is-fault", faulted);
}

function renderMission() {
  const state = STATES[runtime.state];
  const progress = missionProgress();
  const stepIndex = Math.max(0, STATE_ORDER.indexOf(runtime.state));
  byId("status-hero").className = `status-hero status-${state.style}`;
  byId("state-title").textContent = state.title;
  byId("state-copy").textContent = state.copy;
  byId("progress-label").textContent = `Step ${Math.min(stepIndex + 1, 11)} of 11`;
  byId("progress-percent").textContent = `${progress}%`;
  byId("progress-bar").style.width = `${progress}%`;
  byId("next-action-title").textContent = state.action;
  byId("next-action-copy").textContent = state.actionCopy;
  byId("primary-action-label").textContent = state.action;
  byId("primary-action").disabled = false;
  byId("remaining-events").textContent = `${remainingEvents()} of 3`;
  byId("vehicle-status").textContent = runtime.vehicleConnected ? "Connected & Verified" : "Disconnected";
  byId("safety-status").textContent = runtime.fault ? "Active Fault" : "Nominal";
  byId("safety-icon").className = `info-icon ${runtime.fault ? "info-icon--red" : "info-icon--green"}`;
  renderLiveValues();
}

function renderLiveValues() {
  const power = (runtime.sensors.voltage * runtime.sensors.current) / 1000;
  const energyPercent = Math.min(100, (runtime.energyKwh / runtime.targetEnergyKwh) * 100);
  byId("energy-value").textContent = runtime.energyKwh.toFixed(2);
  byId("energy-orbit").style.strokeDashoffset = String(541 - (541 * energyPercent) / 100);
  byId("power-summary").textContent = `${power.toFixed(1)} kW`;
  byId("sensor-voltage").textContent = runtime.sensors.voltage.toFixed(1);
  byId("sensor-current").textContent = runtime.sensors.current.toFixed(1);
  byId("sensor-temperature").textContent = runtime.sensors.temperature.toFixed(1);
  byId("sensor-flow").textContent = runtime.sensors.flow.toFixed(1);
  byId("sensor-pressure").textContent = runtime.sensors.pressure.toFixed(2);
  byId("sensor-hydrogen").textContent = runtime.sensors.hydrogen.toFixed(2);
  renderLCDLiveValues();
}

function renderLCDLiveValues() {
  const power = (runtime.sensors.voltage * runtime.sensors.current) / 1000;
  const energyPercent = Math.min(100, (runtime.energyKwh / runtime.targetEnergyKwh) * 100);
  byId("lcd-power").textContent = power.toFixed(1);
  byId("lcd-energy").textContent = runtime.energyKwh.toFixed(2);
  byId("lcd-energy-bar").style.width = `${energyPercent}%`;
  byId("lcd-voltage").textContent = runtime.sensors.voltage.toFixed(1);
  byId("lcd-current").textContent = runtime.sensors.current.toFixed(1);
  byId("lcd-temperature").textContent = runtime.sensors.temperature.toFixed(1);
  byId("lcd-flow").textContent = runtime.sensors.flow.toFixed(1);
}

function renderLCD() {
  const state = STATES[runtime.state];
  const progress = missionProgress();
  const stepIndex = Math.max(0, STATE_ORDER.indexOf(runtime.state));
  const live = ["POWER_TRANSFER", "DERATING"].includes(runtime.state);
  const faulted = Boolean(runtime.fault);
  const selected = runtime.selectedCassette !== null;

  byId("lcd-screen").classList.toggle("is-fault", faulted);
  byId("lcd-alert").classList.toggle("is-visible", faulted);
  byId("lcd-alert-copy").textContent = runtime.fault ? FAULTS[runtime.fault].value : "Power path isolated";
  byId("lcd-alarm-count").textContent = faulted ? "1" : "0";
  byId("lcd-panel-status").textContent = faulted ? "SAFETY TRIP" : live ? "TRANSFER ENABLED" : "SYSTEM READY";
  byId("lcd-panel-status").parentElement.classList.toggle("is-fault", faulted);
  byId("lcd-state-title").textContent = state.title.toUpperCase();
  byId("lcd-state-copy").textContent = state.copy;
  byId("lcd-progress-bar").style.width = `${progress}%`;
  byId("lcd-progress-label").textContent = faulted
    ? "INDEPENDENT SAFETY OVERRIDE"
    : `STEP ${Math.min(stepIndex + 1, 11)} / 11`;
  byId("lcd-connection").classList.toggle("is-connected", runtime.vehicleConnected);
  byId("lcd-vehicle-status").textContent = runtime.vehicleConnected ? "CONNECTED" : "DISCONNECTED";

  const permissives = {
    "lcd-permissive-hvil": runtime.sensors.hvil,
    "lcd-permissive-iso": runtime.sensors.isolation,
    "lcd-permissive-flow": runtime.sensors.flow >= 0.5,
    "lcd-permissive-thermal": runtime.sensors.temperature < 65,
  };
  Object.entries(permissives).forEach(([id, valid]) => {
    byId(id).classList.toggle("is-valid", valid);
    byId(id).classList.toggle("is-fault", !valid);
  });

  const actuatorStates = {
    "lcd-pump-status": [runtime.actuators.pump, "RUN", "STOP"],
    "lcd-fan-status": [runtime.actuators.fan, "RUN", "STOP"],
    "lcd-input-status": [runtime.actuators.inputContactor, "CLOSED", "OPEN"],
    "lcd-output-status": [runtime.actuators.outputContactor, "CLOSED", "OPEN"],
  };
  Object.entries(actuatorStates).forEach(([id, [active, onLabel, offLabel]]) => {
    byId(id).textContent = active ? onLabel : offLabel;
    byId(id).classList.toggle("is-run", active);
  });

  const trendPath = faulted
    ? "M0 75 L22 72 L45 58 L70 38 L96 29 L125 25 L158 24 L193 24 L226 23 L260 23 L297 24 L330 24 L350 31 L370 67 L395 79 L420 80"
    : live
      ? "M0 75 L22 72 L45 58 L70 38 L96 29 L125 25 L158 24 L193 24 L226 23 L260 23 L297 24 L333 23 L370 23 L420 23"
      : "M0 80 L420 80";
  byId("lcd-trend-line").setAttribute("d", trendPath);
  byId("lcd-trend-line").classList.toggle("is-fault", faulted);

  const actionLabel = LCD_ACTIONS[runtime.state];
  byId("lcd-primary-label").textContent = actionLabel;
  byId("lcd-primary-action").classList.toggle("is-stop", live);

  const lcdNodes = {
    cassette: selected || runtime.completedEvents > 0,
    stack: ["PRE_CHARGE", "POWER_TRANSFER", "DERATING", "RAMP_DOWN", "PURGE_COOLDOWN"].includes(runtime.state),
    converter: live,
    vehicle: runtime.vehicleConnected,
  };
  byId("lcd-energy-path").classList.toggle("is-live", live);
  Object.entries(lcdNodes).forEach(([name, active]) => {
    document.querySelector(`[data-lcd-flow="${name}"]`).classList.toggle("is-active", active);
  });
  byId("lcd-cartridge-state").textContent = faulted
    ? "FAULTED"
    : selected ? `C${runtime.selectedCassette + 1} ACTIVE` : "READY";
  byId("lcd-stack-state").textContent = runtime.actuators.pump ? "REACTION" : "IDLE";
  byId("lcd-converter-state").textContent = runtime.actuators.converter ? "ACTIVE" : "ISOLATED";
  byId("lcd-ev-state").textContent = runtime.vehicleConnected ? "ONLINE" : "OFFLINE";

  byId("lcd-cassette-summary").innerHTML = runtime.cassettes.map((cassetteState, index) => {
    let cssClass = "";
    if (cassetteState === "DRY_READY") cssClass = "is-ready";
    if (["SELECTED", "ACTIVATING", "ACTIVE"].includes(cassetteState)) cssClass = "is-active";
    if (cassetteState === "SPENT") cssClass = "is-spent";
    if (cassetteState === "FAULTED") cssClass = "is-fault";
    return `<span class="lcd-mini-cassette ${cssClass}" title="Cartridge ${index + 1}: ${cassetteState}">C${index + 1}</span>`;
  }).join("");

  renderLCDLiveValues();
}

function updateLCDClock() {
  byId("lcd-clock").textContent = new Date().toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function architectureActiveModules() {
  const active = new Set(["main", "hmi", "safety", "service", "hal"]);
  if (runtime.vehicleConnected || !["STANDBY", "SELF_TEST"].includes(runtime.state)) active.add("ev");
  if (runtime.selectedCassette !== null || ["CASSETTE_SELECTION", "WATER_ACTIVATION", "PRIMING"].includes(runtime.state)) active.add("reaction");
  if (["PRE_CHARGE", "POWER_TRANSFER", "DERATING", "RAMP_DOWN"].includes(runtime.state)) active.add("power");
  if (["WATER_ACTIVATION", "PRIMING", "PRE_CHARGE", "POWER_TRANSFER", "DERATING", "RAMP_DOWN", "PURGE_COOLDOWN", "EMERGENCY_SHUTDOWN"].includes(runtime.state)) active.add("thermal");
  return active;
}

function architectureModuleStatus(moduleName, active) {
  if (moduleName === "safety") return runtime.fault ? "TRIPPED" : "ARMED";
  if (moduleName === "main") return runtime.fault ? "OVERRIDDEN" : "ACTIVE";
  if (moduleName === "hmi") return "MONITOR";
  if (moduleName === "hal") return "ONLINE";
  if (moduleName === "service") return runtime.state === "SERVICE_REQUIRED" ? "LOCKOUT" : "LOGGING";
  if (moduleName === "ev" && runtime.vehicleConnected) return "LINKED";
  if (moduleName === "reaction" && runtime.selectedCassette !== null) return `C${runtime.selectedCassette + 1} ${runtime.cassettes[runtime.selectedCassette]}`;
  if (moduleName === "power" && ["POWER_TRANSFER", "DERATING"].includes(runtime.state)) return "TRANSFER";
  if (moduleName === "thermal" && (runtime.actuators.pump || runtime.actuators.fan)) return "RUNNING";
  return active ? "ACTIVE" : "STANDBY";
}

function renderArchitectureInspector(activeModules) {
  const module = ARCHITECTURE_MODULES[selectedArchitectureModule];
  const moduleActive = activeModules.has(selectedArchitectureModule);
  const moduleAlert = selectedArchitectureModule === "safety" && Boolean(runtime.fault);
  byId("architecture-detail-code").textContent = module.code;
  byId("architecture-detail-title").textContent = module.title;
  byId("architecture-detail-purpose").textContent = module.purpose;
  byId("architecture-detail-responsibilities").innerHTML = module.responsibilities.map((item) => `<li>${item}</li>`).join("");
  byId("architecture-detail-inputs").textContent = module.inputs;
  byId("architecture-detail-outputs").textContent = module.outputs;
  byId("architecture-detail-safety").textContent = module.safety;
  byId("architecture-source-link").href = module.source;
  byId("architecture-detail-runtime").textContent = architectureModuleStatus(selectedArchitectureModule, moduleActive);
  byId("architecture-detail-runtime").parentElement.classList.toggle("is-alert", moduleAlert);
}

function renderArchitecture() {
  const faulted = Boolean(runtime.fault);
  const activeModules = architectureActiveModules();
  byId("architecture-runtime-state").textContent = runtime.state;
  byId("architecture-runtime-state").closest(".architecture-runtime-badge").classList.toggle("is-fault", faulted);

  queryAll(".architecture-module").forEach((moduleElement) => {
    const moduleName = moduleElement.dataset.architectureModule;
    const active = activeModules.has(moduleName);
    const alert = faulted && moduleName === "safety";
    moduleElement.classList.toggle("is-active", active);
    moduleElement.classList.toggle("is-alert", alert);
    moduleElement.classList.toggle("is-selected", moduleName === selectedArchitectureModule);
    moduleElement.querySelector(".module-live").textContent = architectureModuleStatus(moduleName, active);
  });

  const currentPhase = ARCHITECTURE_PHASE_BY_STATE[runtime.state] || "standby";
  const currentIndex = ARCHITECTURE_PHASE_ORDER.indexOf(currentPhase);
  queryAll("[data-architecture-phase]").forEach((phaseElement) => {
    const phaseIndex = ARCHITECTURE_PHASE_ORDER.indexOf(phaseElement.dataset.architecturePhase);
    phaseElement.classList.toggle("is-complete", !faulted && phaseIndex < currentIndex);
    phaseElement.classList.toggle("is-current", !faulted && phaseIndex === currentIndex);
    phaseElement.classList.toggle("is-fault", faulted && phaseIndex === currentIndex);
  });

  renderArchitectureInspector(activeModules);
}

function renderCassettes() {
  byId("cassette-grid").innerHTML = runtime.cassettes.map((state, index) => {
    const [label, description, cssClass] = CASSETTE_UI[state];
    return `<article class="cassette-card ${cssClass}">
      <div class="cassette-top"><span class="cassette-number">CARTRIDGE ${index + 1}</span><span class="cassette-state">${label}</span></div>
      <h3>Al-Air Cartridge</h3><p>${description}</p>
    </article>`;
  }).join("");
}

function renderFlow() {
  const live = ["POWER_TRANSFER", "DERATING"].includes(runtime.state);
  const selected = runtime.selectedCassette !== null;
  const nodes = {
    cassette: selected || runtime.completedEvents > 0,
    stack: ["PRE_CHARGE", "POWER_TRANSFER", "DERATING", "RAMP_DOWN", "PURGE_COOLDOWN"].includes(runtime.state),
    converter: live,
    vehicle: runtime.vehicleConnected,
  };
  byId("system-flow").classList.toggle("is-live", live);
  Object.entries(nodes).forEach(([name, active]) => {
    document.querySelector(`[data-flow="${name}"]`).classList.toggle("is-active", active);
  });
  byId("flow-cassette").textContent = selected ? `Cartridge ${runtime.selectedCassette + 1}` : "Waiting";
  byId("flow-stack").textContent = runtime.actuators.pump ? "Reaction Active" : "Inactive";
  byId("flow-converter").textContent = runtime.actuators.converter ? "Converter Active" : "Isolated";
  byId("flow-vehicle").textContent = runtime.vehicleConnected ? "Connected" : "Disconnected";
  byId("flow-chip").classList.toggle("is-live", live);
  byId("flow-chip").lastChild.textContent = live ? " TRANSFER ACTIVE" : " STANDBY";
}

function renderDiagnostics() {
  const chain = [
    ["HVIL / Interlock", runtime.sensors.hvil],
    ["Galvanic Isolation", runtime.sensors.isolation],
    ["Leak Detection", !runtime.sensors.leak],
    ["Contactor Feedback", runtime.sensors.contactorFeedback],
    ["Hydrogen Monitor", runtime.sensors.hydrogen < 1],
  ];
  byId("safety-chain").innerHTML = chain.map(([name, valid]) =>
    `<div class="chain-row"><span>${name}</span><span class="chain-status${valid ? "" : " is-fault"}">${valid ? "NOMINAL" : "FAULT"}</span></div>`
  ).join("");

  const actuators = [
    ["Water Valve", runtime.actuators.waterValve],
    ["Electrolyte Pump", runtime.actuators.pump],
    ["Ventilation Fan", runtime.actuators.fan],
    ["Vent / Purge", runtime.actuators.vent],
    ["Input Contactor", runtime.actuators.inputContactor],
    ["Output Contactor", runtime.actuators.outputContactor],
    ["DC/DC Converter", runtime.actuators.converter],
    ["Gate Disable", runtime.actuators.gateDisable],
  ];
  byId("actuator-list").innerHTML = actuators.map(([name, active]) =>
    `<div class="actuator-row"><span>${name}</span><span class="actuator-status ${active ? "is-active" : ""}">${active ? "ON" : "OFF"}</span></div>`
  ).join("");
}

function renderService() {
  const remaining = remainingEvents();
  const score = Math.round((remaining / 3) * 100);
  const serviceRequired = runtime.state === "SERVICE_REQUIRED" || Boolean(runtime.fault);
  byId("readiness-ring").style.setProperty("--score", `${score}%`);
  byId("readiness-score").textContent = String(score);
  byId("readiness-title").textContent = serviceRequired ? "System Requires Service" : "System Ready";
  byId("readiness-copy").textContent = serviceRequired
    ? "A professional inspection is required before another rescue event."
    : `${remaining} cartridges are available for rescue events.`;
  byId("service-readiness").textContent = serviceRequired ? "Service Required" : "Ready";
  byId("service-self-test").textContent = runtime.selfTestPassed ? "PASS — check completed" : "Not yet completed";
  byId("service-capacity").textContent = `${remaining} rescue events available`;
}

function renderLog() {
  const log = byId("event-log");
  if (!runtime.log.length) {
    log.innerHTML = "<li><span></span><span></span><span>No events to display</span></li>";
    return;
  }
  log.innerHTML = runtime.log.map((record) => `<li>
    <time>${record.time}</time>
    <span class="log-level${record.level === "CRITICAL" ? " is-critical" : ""}">${record.level}</span>
    <span>${record.message}</span>
  </li>`).join("");
}

function selectView(viewName) {
  queryAll(".view-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.view === viewName));
  queryAll(".view-panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === `view-${viewName}`));
  document.body.classList.toggle("lcd-standalone", viewName === "lcd" && new URLSearchParams(window.location.search).get("view") === "lcd");
}

function initializeFaultSelect() {
  byId("fault-select").innerHTML = Object.entries(FAULTS)
    .map(([key, fault]) => `<option value="${key}">${fault.label}</option>`)
    .join("");
}

function initializeShowcaseScenario() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("scenario") !== "charging") return false;
  runtime.state = "POWER_TRANSFER";
  runtime.cassettes = ["ACTIVE", "DRY_READY", "DRY_READY"];
  runtime.selectedCassette = 0;
  runtime.selfTestPassed = true;
  runtime.vehicleConnected = true;
  runtime.energyKwh = 1.38;
  runtime.sensors = defaultSensors();
  Object.assign(runtime.sensors, { current: 52, temperature: 43.8, flow: 2.2, pressure: 1.08, hydrogen: 0.18 });
  runtime.actuators = defaultActuators();
  Object.assign(runtime.actuators, {
    pump: true, fan: true, vent: true, inputContactor: true,
    outputContactor: true, converter: true, gateDisable: false,
  });
  addLog("POWER_TRANSFER: Presentation scenario loaded");
  startTransferTimer();
  return true;
}

function initializeRequestedView() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  if (!["mission", "lcd", "architecture", "diagnostics", "service"].includes(view)) return;
  selectView(view);
  document.body.classList.toggle("lcd-standalone", view === "lcd");
  document.body.classList.toggle(
    "architecture-capture",
    view === "architecture" && params.get("capture") === "architecture",
  );
}

queryAll(".view-tab").forEach((button) => button.addEventListener("click", () => selectView(button.dataset.view)));
queryAll(".architecture-module").forEach((button) => button.addEventListener("click", () => {
  selectedArchitectureModule = button.dataset.architectureModule;
  renderArchitecture();
}));
byId("primary-action").addEventListener("click", handlePrimaryAction);
byId("emergency-action").addEventListener("click", () => injectFault("E_STOP"));
byId("lcd-primary-action").addEventListener("click", handlePrimaryAction);
byId("lcd-emergency-action").addEventListener("click", () => injectFault("E_STOP"));
byId("lcd-diagnostics-link").addEventListener("click", () => selectView("diagnostics"));
byId("lcd-service-link").addEventListener("click", () => selectView("service"));
byId("inject-fault").addEventListener("click", () => injectFault(byId("fault-select").value));
byId("diagnostics-reset").addEventListener("click", () => resetRuntime());
byId("clear-log").addEventListener("click", () => {
  runtime.log = [];
  renderLog();
  toast("Event log cleared");
});

initializeFaultSelect();
runtime.sensors = defaultSensors();
runtime.actuators = defaultActuators();
if (!initializeShowcaseScenario()) addLog("System ready to begin");
updateLCDClock();
window.setInterval(updateLCDClock, 1000);
render();
initializeRequestedView();
