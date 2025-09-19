import { useNavigate } from "react-router-dom";
import { Dashboard as DashboardComponent } from "../components/Dashboard";
import { MOCK_DASHBOARD_METRICS } from "../data/mockData";

const Dashboard = () => {
  const navigate = useNavigate();

  const handleBack = () => {
    navigate('/');
  };

  return (
    <DashboardComponent 
      metrics={MOCK_DASHBOARD_METRICS} 
      onBack={handleBack}
    />
  );
};

export default Dashboard;