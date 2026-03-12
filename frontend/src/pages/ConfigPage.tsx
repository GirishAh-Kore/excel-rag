import { Box, Container, Typography, Tabs, Tab, AppBar, Toolbar, Button } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LogoutIcon from '@mui/icons-material/Logout';
import GDriveConnection from '../components/GDriveConnection';
import FileUpload from '../components/FileUpload';
import IndexedFilesList from '../components/IndexedFilesList';
import { useAuth } from '../hooks/useAuth';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const ConfigPage = () => {
  const [tabValue, setTabValue] = useState(0);
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, display: { xs: 'none', sm: 'block' } }}>
            Excel RAG System - Configuration
          </Typography>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, display: { xs: 'block', sm: 'none' } }}>
            Config
          </Typography>
          <Button color="inherit" onClick={() => navigate('/chat')}>
            Chat
          </Button>
          <Button
            color="inherit"
            startIcon={<LogoutIcon />}
            onClick={handleLogout}
            sx={{ display: { xs: 'none', sm: 'flex' } }}
          >
            Logout
          </Button>
          <Button
            color="inherit"
            onClick={handleLogout}
            sx={{ display: { xs: 'flex', sm: 'none' } }}
          >
            <LogoutIcon />
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: { xs: 2, sm: 4 }, px: { xs: 1, sm: 3 } }}>
        <Typography variant="h4" gutterBottom sx={{ display: { xs: 'none', sm: 'block' } }}>
          Configuration
        </Typography>

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Google Drive" />
            <Tab label="File Upload" />
            <Tab label="Indexed Files" />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          <GDriveConnection />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <FileUpload />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <IndexedFilesList />
        </TabPanel>
      </Container>
    </Box>
  );
};

export default ConfigPage;
