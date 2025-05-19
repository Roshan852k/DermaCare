import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8092/api';

const getPastData = async (pid) => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get(`${API_URL}/request/history/${pid}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response;
  } catch (error) {
    console.error('Error fetching past data:', error);
    throw error;
  }
};

export default {
  getPastData,
};
