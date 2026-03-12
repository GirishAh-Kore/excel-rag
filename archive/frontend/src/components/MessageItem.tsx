import {
  Box,
  Paper,
  Typography,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import type { Message } from '../types';

interface MessageItemProps {
  message: Message;
}

const MessageItem = ({ message }: MessageItemProps) => {
  const isUser = message.role === 'user';

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Paper
        elevation={1}
        sx={{
          p: 2,
          maxWidth: { xs: '90%', sm: '80%', md: '70%' },
          bgcolor: isUser ? 'primary.light' : 'background.paper',
          color: isUser ? 'primary.contrastText' : 'text.primary',
        }}
      >
        <Box display="flex" alignItems="center" gap={1} mb={1}>
          {isUser ? <PersonIcon fontSize="small" /> : <SmartToyIcon fontSize="small" />}
          <Typography variant="caption">
            {isUser ? 'You' : 'Assistant'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {new Date(message.timestamp).toLocaleTimeString()}
          </Typography>
        </Box>

        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
          {message.content}
        </Typography>

        {!isUser && message.confidence !== undefined && (
          <Box mt={1}>
            <Chip
              label={`Confidence: ${message.confidence}%`}
              size="small"
              color={message.confidence > 80 ? 'success' : message.confidence > 60 ? 'warning' : 'error'}
            />
          </Box>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <Accordion sx={{ mt: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2">
                Sources ({message.sources.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List dense>
                {message.sources.map((source, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={`[${source.citation_number}] ${source.file_name}`}
                      secondary={`Sheet: ${source.sheet_name}, Range: ${source.cell_range}`}
                    />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        )}
      </Paper>
    </Box>
  );
};

export default MessageItem;
