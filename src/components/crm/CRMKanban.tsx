"use client";

import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { useRouter } from "next/navigation";
import { ThumbsDown } from "lucide-react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  DragStartEvent,
  DragEndEvent,
  DragOverEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { DotsHorizontalIcon, PlusCircledIcon } from "@radix-ui/react-icons";

// We will replace these imports with our own UI components

// interface CRMKanbanProps {
//   salesStages: crm_Opportunities_Sales_Stages[];
//   opportunities: crm_Opportunities[];
//   crmData: any;
// }

// type Column = crm_Opportunities_Sales_Stages & {
//   opportunities: crm_Opportunities[];
// };

// function initColumns(
//   opps: crm_Opportunities[],
//   stages: crm_Opportunities_Sales_Stages[]
// ): Column[] {
//   return stages.map((stage) => ({
//     ...stage,
//     opportunities: opps.filter(
//       (o: any) => o.sales_stage === stage.id && o.status === "ACTIVE"
//     ),
//   }));
// }

// Mock data for now
const mockSalesStages = [
    { id: 'new', name: 'New', opportunities: [] },
    { id: 'contacted', name: 'Contacted', opportunities: [] },
    { id: 'quoted', name: 'Quoted', opportunities: [] },
    { id: 'closed_won', name: 'Closed Won', opportunities: [] },
    { id: 'dead', name: 'Dead', opportunities: [] },
];

const mockOpportunities = [
    { id: '1', name: 'Lead 1', description: 'A test lead', budget: 1000, close_date: new Date(), sales_stage: 'new', status: 'ACTIVE'},
    { id: '2', name: 'Lead 2', description: 'Another test lead', budget: 2000, close_date: new Date(), sales_stage: 'new', status: 'ACTIVE'},
];

const CRMKanban = () => {
    const [columns, setColumns] = useState(mockSalesStages);

  return (
    <div className="flex w-full h-full overflow-x-auto">
        {columns.map((col) => (
            <div key={col.id} className="mx-1 w-full min-w-[300px] bg-gray-100 rounded-lg p-2">
                <h2 className="text-lg font-bold mb-2">{col.name}</h2>
                <div>
                    {/* Opportunity cards will go here */}
                </div>
            </div>
        ))}
    </div>
  );
};

export default CRMKanban;
