import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8092/api';

const fetchimage = async (aid) => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.get(`${API_URL}/image/fetch/${aid}`, {
      responseType: 'blob',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    return response;
  } catch (error) {
    console.error('Error fetching image:', error);
    throw error;
  }
};

export default {
  fetchimage,
};
