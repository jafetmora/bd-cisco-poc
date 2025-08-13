const steps = [
  "Deal",
  "Quote",
  "Install/Billing",
  "Review",
  "Approvals",
  "Orders",
];

export default function StepHeader({
  currentStep = 1,
}: {
  currentStep?: number;
}) {
  return (
    <div className="flex justify-between px-8 pt-6 pb-4">
      {steps.map((step, index) => (
        <div key={step} className="flex-1 flex flex-col items-center">
          <div
            className={`w-6 h-6 rounded-full flex items-center justify-center font-semibold text-xs ${index <= currentStep ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-600"}`}
          >
            {index + 1}
          </div>
          <div
            className={`text-xs mt-1 ${index === currentStep ? "text-blue-700 font-medium" : "text-gray-400"}`}
          >
            {step}
          </div>
        </div>
      ))}
    </div>
  );
}
