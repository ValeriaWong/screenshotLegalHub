import { Component, type ReactNode } from "react";
import { Button } from "../ui";
import { useI18n } from "../../i18n";
export function Feedback({
  state,
  error,
  retry,
}: {
  state: "loading" | "empty" | "error" | "notRun";
  error?: string;
  retry?: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="feedback" role={state === "error" ? "alert" : "status"}>
      <p>
        {t(state)}
        {error ? ": " + error : ""}
      </p>
      {retry && <Button onClick={retry}>{t("retry")}</Button>}
    </div>
  );
}
export class FeatureBoundary extends Component<
  { children: ReactNode; label: string },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    return this.state.error ? (
      <div role="alert">
        {this.props.label}
        <Button onClick={() => this.setState({ error: false })}>↻</Button>
      </div>
    ) : (
      this.props.children
    );
  }
}
