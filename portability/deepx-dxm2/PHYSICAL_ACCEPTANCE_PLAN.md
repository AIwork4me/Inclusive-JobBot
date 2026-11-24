# Physical acceptance plan

`DXM2_PHYSICAL_VALIDATION_NOT_RUN`

On physical hardware, verify compiler, driver, firmware and board identity. Confirm NPU allocation with vendor telemetry tied to the server process and cross-check a reference run on the same weights. Exercise the frozen conformance, security and independence suites. Measure cold and warm behavior at supported context/concurrency limits and run a representative job workload. Record whole-system power with an external meter. Run 24-hour and 168-hour soak for the later production candidate. AMD results provide regression comparisons for the harness and business logic. Collect DX-M2 performance evidence on the physical device.
