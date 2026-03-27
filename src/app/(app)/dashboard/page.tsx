
import React from 'react';
import CRMKanban from '@/components/crm/CRMKanban';

const DashboardPage = () => {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Lead Dashboard</h1>
      <CRMKanban />      
    </div>
  );
};

export default DashboardPage;
