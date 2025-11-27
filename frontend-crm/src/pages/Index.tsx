import { useNavigate } from "react-router-dom";
import { KanbanBoard } from "../components/KanbanBoard";

const Index = () => {
  const navigate = useNavigate();

  const handleDashboard = () => {
    navigate('/dashboard');
  };

  return <KanbanBoard onDashboard={handleDashboard} />;
};

export default Index;
