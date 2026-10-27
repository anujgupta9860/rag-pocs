# Aurora Solar Pump Co. — Installation and Operation Manual (Model Series ASP)

> Fictional sample document for RAG POC testing. All values are invented.

## 1. Product overview

The Aurora Solar Pump series moves water using only solar power.
The flagship model is the **Aurora Pro 3000**, rated at **3,000 litres per hour**
at a maximum head of **85 metres**. The entry model, the **Aurora Lite 800**,
is rated at **800 litres per hour** at a maximum head of **30 metres**.

## 2. Safety

- Disconnect the PV array before servicing the controller. The array can
  produce up to **110 volts DC** in full sun.
- Never run the pump dry for more than **60 seconds**; dry running voids the warranty.
- The controller enclosure is rated **IP65**.

## 3. Installation steps

1. Mount the panels facing the equator with a tilt equal to your latitude **plus 10 degrees**.
2. Place the pump at least **2 metres** below the minimum water level.
3. Connect the water level sensor before the power cables.
4. Prime the delivery pipe, then power on and run the self-test (hold the
   Mode button for **5 seconds**).

## 4. Maintenance schedule

| Task | Interval |
|---|---|
| Clean the intake filter | Every 30 days |
| Inspect panel surface and wiring | Every 90 days |
| Replace the mechanical seal | Every 24 months |
| Firmware update check | Every 12 months |

The mechanical seal replacement kit is part number **ASP-SEAL-24**.

## 5. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Pump starts and stops repeatedly | Low water level sensor triggered | Lower the sensor by 20 cm |
| Flow is 40% below rating | Partially blocked intake filter | Clean the intake filter |
| Controller shows error E47 | Overvoltage from the PV array | Add the ASP-SURGE module |
| No power at all | Blown 15 A fuse in the controller | Replace with a 15 A slow-blow fuse |

Error **E47** always means overvoltage from the PV array.
