import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  FaChevronDown,
  FaShareAlt,
  FaPrint,
  FaEnvelope,
  FaTrash,
  FaPen,
} from "react-icons/fa";
import type { QuoteHeaderData } from "../../../types/Quotes";

type Props = { data: QuoteHeaderData; title?: string; noMargins?: boolean };

function headerSignature(d: QuoteHeaderData) {
  return [
    d.title,
    d.dealId,
    d.quoteNumber,
    d.status,
    d.expiryDate,
    d.priceProtectionExpiry ?? "-",
    d.priceList.name,
    d.priceList.region,
    d.priceList.currency,
  ].join("|");
}

export default function QuoteHeaderBar({ data, title, noMargins }: Props) {
  const [showMenu, setShowMenu] = useState(false);
  const sig = useMemo(() => headerSignature(data), [data]);
  const [sweep, setSweep] = useState(false);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setSweep(true);
    const t = setTimeout(() => setSweep(false), 900);
    return () => clearTimeout(t);
  }, [sig]);

  const statusBadge = {
    NOT_SUBMITTED: { text: "⚠ Not Submitted", className: "text-yellow-600" },
    DRAFT: { text: "Draft", className: "text-gray-600" },
    SUBMITTED: { text: "Submitted", className: "text-blue-600" },
    APPROVED: { text: "Approved", className: "text-green-600" },
    REJECTED: { text: "Rejected", className: "text-red-600" },
    EXPIRED: { text: "Expired", className: "text-red-500" },
  }[data.status];

  const fmtDate = (iso?: string | null) =>
    iso
      ? new Date(iso).toLocaleDateString(undefined, {
          month: "short",
          day: "2-digit",
          year: "numeric",
        })
      : "—";

  return (
    <div className={"relative bg-white shadow rounded-xl " + (noMargins ? "mx-0" : "mx-8") + " p-6 border border-gray-200 overflow-hidden"}>
      <AnimatePresence>
        {sweep && (
          <motion.div
            key="sweep-bar"
            initial={{ x: "-100%" }}
            animate={{ x: "100%" }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            className="pointer-events-none absolute top-0 left-0 h-[2px] w-full 
                       bg-gradient-to-r from-transparent via-sky-400 to-transparent"
          />
        )}
      </AnimatePresence>

      <AnimatePresence mode="popLayout">
        <motion.div
          key={sig}
          initial={{ opacity: 0.0, filter: "blur(6px)", y: 4 }}
          animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
          exit={{ opacity: 0, filter: "blur(4px)", y: -2 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="flex items-start justify-between"
        >
          <div>
            <div className="flex space-x-3">
              <h2 className="text-xl font-semibold mb-2">{title}</h2>
              <FaPen className="cursor-pointer w-3 h-3" />
            </div>

            <div className="w-full flex flex-wrap gap-x-8 gap-y-3 text-sm text-gray-600 mt-6">
              <div className="flex flex-col min-w-[150px] text-lg">
                <span className="text-gray-400">Deal ID:</span> {data.dealId}
              </div>
              <div className="flex flex-col min-w-[150px] text-lg">
                <span className="text-gray-400">Quote Number:</span>{" "}
                {data.quoteNumber}
              </div>
              <div className="flex flex-col min-w-[180px] text-lg">
                <span className="text-gray-400">Quote Status:</span>{" "}
                <span className={statusBadge.className}>
                  {statusBadge.text}
                </span>
              </div>
              <div className="flex flex-col min-w-[150px] text-lg">
                <span className="text-gray-400">Expiry Date:</span>{" "}
                {fmtDate(data.expiryDate)}
              </div>
              <div className="flex flex-col min-w-[200px] text-lg">
                <span className="text-gray-400">Price Protection Expiry:</span>{" "}
                {fmtDate(data.priceProtectionExpiry)}
              </div>
              <div className="flex flex-col min-w-[280px] text-lg">
                <span className="text-gray-400">Price List:</span>{" "}
                {data.priceList.name} in {data.priceList.region} Availability (
                {data.priceList.currency})
              </div>
            </div>
          </div>

          <div className="relative">
            <button
              className="text-blue-600 hover:text-blue-800 text-sm flex items-center gap-2"
              onClick={() => setShowMenu(!showMenu)}
            >
              More <FaChevronDown className="w-3 h-3" />
            </button>
            {showMenu && (
              <div className="absolute right-0 mt-2 bg-white border border-gray-200 rounded-md shadow-lg w-48 z-10 text-sm">
                <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
                  <FaShareAlt /> Share
                </button>
                <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
                  <FaPrint /> Print
                </button>
                <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
                  <FaEnvelope /> Email
                </button>
                <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
                  <FaTrash /> Delete
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
