import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PlaceInput } from "./PlaceInput";
import { TripForm } from "./TripForm";

describe("TripForm", () => {
  it("submits a typed trip with an ISO departure", async () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} busy={false} />);
    await userEvent.type(screen.getByLabelText("Origin"), "Dallas, TX");
    await userEvent.type(screen.getByLabelText("Destination"), "Denver, CO");
    const load = screen.getByLabelText("Load weight (lb)");
    await userEvent.clear(load);
    await userEvent.type(load, "42000");
    await userEvent.click(screen.getByLabelText("50 mi"));
    await userEvent.click(screen.getByRole("button", { name: "Find safest route" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const trip = onSubmit.mock.calls[0]![0];
    expect(trip).toMatchObject({
      origin: "Dallas, TX",
      destination: "Denver, CO",
      load_lb: 42000,
      interval_mi: 50,
    });
    expect(trip.departure).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\.000Z$/);
  });

  it("disables submit while busy", () => {
    render(<TripForm onSubmit={() => {}} busy />);
    expect(screen.getByRole("button", { name: /Analyzing/ })).toBeDisabled();
  });
});

describe("PlaceInput", () => {
  it("offers suggestions and stores the chosen place with coordinates", async () => {
    const place = { label: "Dallas, TX, USA", lat: 32.8, lon: -96.8 };
    const search = vi.fn().mockResolvedValue([place]);
    const onChange = vi.fn();
    const { rerender } = render(
      <PlaceInput label="Origin" value="" onChange={onChange} search={search} />,
    );
    rerender(<PlaceInput label="Origin" value="Dall" onChange={onChange} search={search} />);
    await userEvent.click(screen.getByRole("combobox"));

    const option = await screen.findByRole("option", { name: "Dallas, TX, USA" });
    expect(search).toHaveBeenCalledWith("Dall", expect.any(AbortSignal));
    await userEvent.click(option);
    expect(onChange).toHaveBeenLastCalledWith(place);
  });

  it("doesn't search for very short text", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(<PlaceInput label="Origin" value="Da" onChange={() => {}} search={search} />);
    await new Promise((r) => setTimeout(r, 300));
    expect(search).not.toHaveBeenCalled();
  });
});
